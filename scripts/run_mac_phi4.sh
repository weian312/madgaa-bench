#!/usr/bin/env bash
set -uo pipefail
PROJECT=/Users/weian/Documents/benchmark_project
RAPID_MLX=$PROJECT/venv/bin/rapid-mlx
PYTHON=$PROJECT/venv/bin/python3
PORT=7777
LOG=/tmp/mac_phi4.log
echo "[$(date)] mac phi4 start" > $LOG

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
  local hf_path="$1"
  pkill -f "rapid-mlx serve" 2>/dev/null || true
  sleep 3
  nohup $RAPID_MLX serve "$hf_path" --port $PORT --no-thinking > /tmp/rapid_phi4_$$.log 2>&1 &
  disown
  for i in $(seq 1 60); do
    if curl -s -m 2 http://localhost:$PORT/v1/models 2>/dev/null | grep -qiE "phi"; then return 0; fi
    sleep 5
  done
  return 1
}

label=phi4_full
path=mlx-community/phi-4-4bit
echo "[$(date)] starting $path" >> $LOG
if start_server "$path"; then
  bench_all_tasks "$label" "$path"
else
  echo "FAILED $label"
fi
pkill -f "rapid-mlx serve" 2>/dev/null || true
echo "[$(date)] mac phi4 DONE" >> $LOG
echo MAC_PHI4_DONE
