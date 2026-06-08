import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

'''
snap_download参数详解-https://download.csdn.net/blog/column/12453626/133658587
'''
from huggingface_hub import snapshot_download

snapshot_download(
  repo_id="cross-encoder/ms-marco-MiniLM-L-6-v2",
  repo_type="model",
  local_dir="/home/xjs/big_space/code/LLM_study/langgraph_multi-agent-rag-customer-support/ms-marco-MiniLM-L-6-v2",
  # allow_patterns=['facenet.pth'],
  # ignore_patterns=["models/*"], 
  max_workers=8
)