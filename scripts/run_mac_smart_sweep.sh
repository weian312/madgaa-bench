#!/usr/bin/env bash
# Smart Mac sweep: iterate through models, skip if already benched, skip if
# weights incomplete (size < threshold), run bench otherwise.
# Re-run as many times as needed; idempotent.

set -uo pipefail
cd /Users/weian/Documents/benchmark_project/v2
PROJECT=/Users/weian/Documents/benchmark_project
RAPID_MLX=$PROJECT/venv/bin/rapid-mlx
PYTHON=$PROJECT/venv/bin/python3
PORT=7777
LOG=/tmp/mac_smart_sweep.log
echo "[$(date)] mac smart sweep run" >> $LOG

run_bench() {
  local label="$1" hf_path="$2" task_id="$3" prompt="$4" max_tokens="$5"
  $PYTHON scripts/bench_medical.py \
    --base-url http://localhost:$PORT/v1 \
    --model "$hf_path" \
    --prompt "$prompt" --task-id "$task_id" \
    --hardware macmini-m4-32gb --framework rapidmlx \
    --quant 4bit-mlx \
    --max-tokens $max_tokens --warmup 1 --runs 5 \
    --out raw_logs/mac/${label}_${task_id}.jsonl 2>&1 | tee -a $LOG
}

bench_all_tasks() {
  run_bench $1 "$2" soap_en prompts/task_A_soap_en.txt 600
  run_bench $1 "$2" ddx_en prompts/task_B_ddx_en.txt 400
  run_bench $1 "$2" drug_zh prompts/task_C_drug_zh.txt 500
  run_bench $1 "$2" icd_zh prompts/task_D_icd_zh.txt 200
}

start_server() {
  local hf_path="$1" needle="$2"
  pkill -f "rapid-mlx serve" 2>/dev/null || true
  sleep 3
  nohup $RAPID_MLX serve "$hf_path" --port $PORT --no-thinking > /tmp/rapid_smart_$$.log 2>&1 &
  disown
  for i in $(seq 1 90); do
    if curl -s -m 2 http://localhost:$PORT/v1/models 2>/dev/null | grep -qiE "$needle"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# (label, hf_path, min_disk_gb, search-needle)
declare -a MODELS=(
  "qwen36_35b mlx-community/Qwen3.6-35B-A3B-4bit 18 Qwen3.6"
  "gemma4_26b mlx-community/gemma-4-26b-a4b-it-4bit 13 gemma-4-26b"
  "phi4_full mlx-community/phi-4-4bit 7 phi-4"
  "mistral_small_24b mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit 13 Mistral-Small"
  "deepseek_r1_32b mlx-community/DeepSeek-R1-Distill-Qwen-32B-4bit 16 DeepSeek-R1"
)

for spec in "${MODELS[@]}"; do
  label=$(echo "$spec" | awk '{print $1}')
  path=$(echo "$spec" | awk '{print $2}')
  min_gb=$(echo "$spec" | awk '{print $3}')
  needle=$(echo "$spec" | awk '{print $4}')

  done_count=0
  for t in soap_en ddx_en drug_zh icd_zh; do
    [ -s "raw_logs/mac/${label}_${t}.jsonl" ] && done_count=$((done_count+1))
  done
  if [ "$done_count" = "4" ]; then
    echo "[$(date)] $label complete, skip" >> $LOG
    continue
  fi

  # check disk size
  cache_safe=$(echo "$path" | sed 's|/|--|g')
  cache_dir="$HOME/.cache/huggingface/hub/models--$cache_safe"
  size_gb=0
  [ -d "$cache_dir" ] && size_gb=$(du -sBG "$cache_dir" 2>/dev/null | awk '{gsub("G",""); print $1}')
  if [ "$size_gb" -lt "$min_gb" ]; then
    echo "[$(date)] $label size ${size_gb}G < ${min_gb}G, skip" >> $LOG
    continue
  fi

  echo "============================================" >> $LOG
  echo "[$(date)] MODEL: $label ($path)" >> $LOG
  if ! start_server "$path" "$needle"; then
    echo "[$(date)] $label FAILED to start" >> $LOG
    continue
  fi
  bench_all_tasks "$label" "$path"
done

pkill -f "rapid-mlx serve" 2>/dev/null || true
echo "[$(date)] mac smart sweep DONE" >> $LOG
echo MAC_SMART_SWEEP_DONE
