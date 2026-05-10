#!/usr/bin/env bash
# H200 sweep: kill any running llama-server on benchmark port, start a new
# one for the next model, run 4 medical tasks.
#
# Run on h200, from /data/txtner-bench/madgaa-bench/v2 .

set -uo pipefail
cd /data/txtner-bench/madgaa-bench/v2
LLAMA=/home/william/llama.cpp/build-cuda/bin/llama-server
PYTHON=$HOME/venvs/bench/bin/python3
HF_CACHE=/data/txtner-bench/hf-cache/hub
PORT=29903
LOG=/data/txtner-bench/madgaa-bench/v2/run_h200_sweep.log
echo "[$(date)] h200 sweep start" > $LOG

run_bench() {
  local label_model="$1" served_name="$2" task_id="$3" prompt="$4" max_tokens="$5"
  $PYTHON scripts/bench_medical.py \
    --base-url http://127.0.0.1:$PORT/v1 \
    --model "$served_name" \
    --prompt "$prompt" --task-id "$task_id" \
    --hardware h200-nvl --framework llamacpp --quant Q4_K_M \
    --max-tokens $max_tokens --warmup 1 --runs 5 \
    --out raw_logs/h200/${label_model}_${task_id}.jsonl 2>&1 | tee -a $LOG
}

bench_all_tasks() {
  local label="$1" served_name="$2"
  run_bench $label "$served_name" soap_en prompts/task_A_soap_en.txt 600
  run_bench $label "$served_name" ddx_en prompts/task_B_ddx_en.txt 400
  run_bench $label "$served_name" drug_zh prompts/task_C_drug_zh.txt 500
  run_bench $label "$served_name" icd_zh prompts/task_D_icd_zh.txt 200
}

start_server() {
  local gguf_path="$1" alias_name="$2" ctx="$3"
  echo "[$(date)] starting $alias_name from $gguf_path :$PORT" >> $LOG
  pkill -f "llama-server.*--port $PORT" 2>/dev/null || true
  sleep 3
  nohup $LLAMA -m "$gguf_path" --host 127.0.0.1 --port $PORT \
    -c $ctx -np 1 -ngl 999 -fa auto -b 2048 \
    --alias "$alias_name" --reasoning off > /tmp/llama_${alias_name}.log 2>&1 &
  disown
  for i in $(seq 1 90); do
    if curl -s -m 2 http://127.0.0.1:$PORT/v1/models 2>/dev/null \
       | grep -q "$alias_name"; then
      return 0
    fi
    sleep 3
  done
  echo "[$(date)] FAILED to start $alias_name" >> $LOG
  return 1
}

# (label, gguf-glob-path, served-name, ctx)
declare -a MODELS=(
  "gemma4_26b $HF_CACHE/models--unsloth--gemma-4-26B-A4B-it-GGUF/snapshots/*/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf gemma-4-26B-A4B-it 16384"
  "gemma4_31b $HF_CACHE/models--unsloth--gemma-4-31B-it-GGUF/snapshots/*/gemma-4-31B-it-Q4_K_M.gguf gemma-4-31B-it 16384"
  "qwen3next_80b $HF_CACHE/models--unsloth--Qwen3-Next-80B-A3B-Instruct-GGUF/snapshots/*/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf qwen3-next-80b-a3b 16384"
  "phi4_full $HF_CACHE/models--unsloth--phi-4-GGUF/snapshots/*/phi-4-Q4_K_M.gguf phi-4 16384"
  "glm47_flash $HF_CACHE/models--unsloth--GLM-4.7-Flash-GGUF/snapshots/*/GLM-4.7-Flash-Q4_K_M.gguf glm-4.7-flash 16384"
  "gptoss_20b $HF_CACHE/models--unsloth--gpt-oss-20b-GGUF/snapshots/*/gpt-oss-20b-Q4_K_M.gguf gpt-oss-20b 16384"
  "mistral_small_24b $HF_CACHE/models--unsloth--Mistral-Small-3.2-24B-Instruct-2506-GGUF/snapshots/*/Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf mistral-small-3.2-24b 16384"
  "deepseek_r1_32b $HF_CACHE/models--unsloth--DeepSeek-R1-Distill-Qwen-32B-GGUF/snapshots/*/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf deepseek-r1-32b 16384"
)

for spec in "${MODELS[@]}"; do
  label=$(echo "$spec" | awk '{print $1}')
  path=$(echo "$spec" | awk '{print $2}')
  alias_name=$(echo "$spec" | awk '{print $3}')
  ctx=$(echo "$spec" | awk '{print $4}')
  resolved=$(ls $path 2>/dev/null | head -1 || true)
  if [ -z "$resolved" ]; then
    echo "[$(date)] missing $label ($path)" >> $LOG
    continue
  fi
  done_count=0
  for t in soap_en ddx_en drug_zh icd_zh; do
    [ -s "raw_logs/h200/${label}_${t}.jsonl" ] && done_count=$((done_count+1))
  done
  if [ "$done_count" = "4" ]; then
    echo "[$(date)] $label already complete (4 jsonl), skipping" >> $LOG
    continue
  fi
  echo "============================================" >> $LOG
  echo "MODEL: $label ($alias_name) <- $resolved" >> $LOG
  if ! start_server "$resolved" "$alias_name" "$ctx"; then
    echo "[$(date)] skipping $label" >> $LOG
    continue
  fi
  bench_all_tasks "$label" "$alias_name"
done

pkill -f "llama-server.*--port $PORT" 2>/dev/null || true
echo "[$(date)] h200 sweep DONE" >> $LOG
echo H200_SWEEP_DONE
