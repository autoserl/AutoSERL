export XLA_PYTHON_CLIENT_PREALLOCATE=false && \
export XLA_PYTHON_CLIENT_MEM_FRACTION=.6 && \
python ../../train_rlpd.py "$@" \
    --exp_name=plug_insert \
    --checkpoint_path=demo_run_auto_intervention \
    --demo_path=/home/cxl/hil-serl/examples/experiments/plug_insert/demo_data/plug_insert_1_demos_2026-01-20_22-40-39.pkl \
    --learner 