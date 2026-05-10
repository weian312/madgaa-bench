#!/usr/bin/env bash
# Round 2: phi-4 + (whatever else has finished pulling)
set -euo pipefail
PROJECT=/Users/weian/Documents/benchmark_project
RAPID_MLX=$PROJECT/venv/bin/rapid-mlx
PYTHON=$PROJECT/venv/bin/python3
PORT=7777
LOG=/tmp/mac_round2.log
echo "[$(date)] mac round 2 start" > $LOG

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
  local label="$1" hf_path="$2"
  run_bench $label "$hf_path" soap_en prompts/task_A_soap_en.txt 600
  run_bench $label "$hf_path" ddx_en prompts/task_B_ddx_en.txt 400
  run_bench $label "$hf_path" drug_zh prompts/task_C_drug_zh.txt 500
  run_bench $label "$hf_path" icd_zh prompts/task_D_icd_zh.txt 200
}

start_server() {
  local hf_path="$1"
  echo "[$(date)] starting $hf_path" >> $LOG
  pkill -f "rapid-mlx serve" 2>/dev/null || true
  sleep 3
  nohup $RAPID_MLX serve "$hf_path" --port $PORT --no-thinking > /tmp/rapid_round2_$$.log 2>&1 &
  disown
  for i in $(seq 1 60); do
    if curl -s -m 2 http://localhost:$PORT/v1/models 2>/dev/null | grep -qiE "$(basename $hf_path | head -c 8)"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# Models known fully pulled (check sizes manually)
CANDIDATES=(
  "phi4_full mlx-community/phi-4-4bit 8000000000"
  "mistral_small_24b mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit 14000000000"
  "deepseek_r1_32b mlx-community/DeepSeek-R1-Distill-Qwen-32B-4bit 18000000000"
)

for spec in "${CANDIDATES[@]}"; do
  label=$(echo "$spec" | awk '{print $1}')
  path=$(echo "$spec" | awk '{print $2}')
  min_size=$(echo "$spec" | awk '{print $3}')
  CACHE_DIR=$HOME/.cache/huggingface/hub/models--$(echo $path | tr '/' '-')
  ACTUAL=$(du -sb $CACHE_DIR 2>/dev/null | awk '{print $1}')
  if [ -z "$ACTUAL" ] || [ "$ACTUAL" -lt "$min_size" ]; then
    echo "[$(date)] SKIP $label (size $ACTUAL < $min_size)" >> $LOG
    continue
  fi
  echo "============================================" >> $LOG
  echo "[$(date)] MODEL: $label ($path) actual=$ACTUAL" >> $LOG
  if ! start_server "$path"; then
    echo "[$(date)] FAILED $label" >> $LOG
    continue
  fi
  bench_all_tasks "$label" "$path"
done

pkill -f "rapid-mlx serve" 2>/dev/null || true
echo "[$(date)] mac round 2 DONE" >> $LOG
echo MAC_ROUND2_DONE
