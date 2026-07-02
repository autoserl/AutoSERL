export XLA_PYTHON_CLIENT_PREALLOCATE=false && \
export XLA_PYTHON_CLIENT_MEM_FRACTION=.2 && \
python ../../train_rlpd.py "$@" \
    --exp_name=plug_insert \
    --checkpoint_path=demo_run_auto_intervention \
    --actor \
    # --eval_checkpoint_step=49000 \
    # --eval_n_trajs=50
