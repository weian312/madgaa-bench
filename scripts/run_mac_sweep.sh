#!/usr/bin/env bash
# Mac sweep: for each model alias in MODELS, start rapid-mlx server, run 4
# medical tasks, kill server, move to next.
#
# Run from /Users/weian/Documents/benchmark_project/v2 .

set -euo pipefail
PROJECT=/Users/weian/Documents/benchmark_project
RAPID_MLX=$PROJECT/venv/bin/rapid-mlx
PYTHON=$PROJECT/venv/bin/python3
PORT=7777
LOG=/tmp/mac_sweep.log
echo "[$(date)] mac sweep start" > $LOG

run_bench() {
  local label_model="$1" hf_path="$2" task_id="$3" prompt="$4" max_tokens="$5"
  $PYTHON scripts/bench_medical.py \
    --base-url http://localhost:$PORT/v1 \
    --model "$hf_path" \
    --prompt "$prompt" --task-id "$task_id" \
    --hardware macmini-m4-32gb --framework rapidmlx \
    --quant 4bit-mlx \
    --max-tokens $max_tokens --warmup 1 --runs 5 \
    --out raw_logs/mac/${label_model}_${task_id}.jsonl 2>&1 | tee -a $LOG
}

bench_all_tasks() {
  local label="$1" hf_path="$2"
  run_bench $label "$hf_path" soap_en prompts/task_A_soap_en.txt 600
  run_bench $label "$hf_path" ddx_en prompts/task_B_ddx_en.txt 400
  run_bench $label "$hf_path" drug_zh prompts/task_C_drug_zh.txt 500
  run_bench $label "$hf_path" icd_zh prompts/task_D_icd_zh.txt 200
}

start_server() {
  local hf_path="$1"
  echo "[$(date)] starting $hf_path on :$PORT" >> $LOG
  pkill -f "rapid-mlx serve" 2>/dev/null || true
  sleep 3
  nohup $RAPID_MLX serve "$hf_path" --port $PORT --no-thinking \
    > /tmp/rapid_$$.log 2>&1 &
  disown
  local pid=$!
  echo "[$(date)] PID=$pid" >> $LOG
  for i in $(seq 1 60); do
    if curl -s -m 2 http://localhost:$PORT/v1/models 2>/dev/null \
       | grep -qi "$(basename $hf_path | head -c 8)"; then
      return 0
    fi
    sleep 5
  done
  echo "[$(date)] FAILED to start $hf_path" >> $LOG
  return 1
}

# (label, full HF path, optional max_kv_tokens)
declare -a MODELS=(
  "gemma4_26b mlx-community/gemma-4-26b-a4b-it-4bit"
  "phi4_14b mlx-community/phi-4-4bit"
  "glm47_flash mlx-community/GLM-4.7-4bit"
  "gptoss_20b mlx-community/GPT-OSS-20B-4bit"
  "deepseek_r1_32b mlx-community/DeepSeek-R1-Distill-Qwen-32B-4bit"
  "mistral_small_24b mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit"
)

for spec in "${MODELS[@]}"; do
  label=$(echo "$spec" | awk '{print $1}')
  path=$(echo "$spec" | awk '{print $2}')
  echo "============================================" >> $LOG
  echo "MODEL: $label ($path)" >> $LOG
  if ! start_server "$path"; then
    echo "[$(date)] skipping $label" >> $LOG
    continue
  fi
  bench_all_tasks "$label" "$path"
done

pkill -f "rapid-mlx serve" 2>/dev/null || true
echo "[$(date)] mac sweep DONE" >> $LOG
echo MAC_SWEEP_DONE
