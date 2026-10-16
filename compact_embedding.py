"""Same MiniLM ONNX weights, with the original compact SentencePiece tokenizer.

Query token IDs and pooled vectors are checked against fastembed before hosting.
This avoids loading its ~250 MB Rust tokenizer vocabulary in the web process.
"""
from pathlib import Path
import re
import numpy as np
import onnxruntime as ort
import sentencepiece as spm


class CompactEmbedding:
    def __init__(self,cache):
        cache=Path(cache)
        model=cache/'compact'/'model_optimized.onnx'
        if not model.is_file():model=next(cache.rglob('model_optimized.onnx'))
        tokenizer=cache/'compact'/'sentencepiece.bpe.model'
        if not tokenizer.is_file():tokenizer=cache/'sentencepiece.bpe.model'
        options=ort.SessionOptions()
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        options.enable_cpu_mem_arena=False
        options.enable_mem_pattern=False
        options.intra_op_num_threads=1
        options.inter_op_num_threads=1
        options.add_session_config_entry('session.disable_prepacking','1')
        self.session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
        self.tokenizer=spm.SentencePieceProcessor(model_file=str(tokenizer))
        self.inputs={i.name for i in self.session.get_inputs()}

    def token_ids(self,text):
        special={'<s>':0,'<pad>':1,'</s>':2,'<unk>':3,'<mask>':250001}
        ids=[]
        for part in re.split(r'(<s>|</s>|<pad>|<unk>|<mask>)',text):
            if part in special:ids.append(special[part])
            elif part:ids.extend(3 if i==0 else i+1 for i in self.tokenizer.encode(part,out_type=int))
        return [0,*ids[:126],2]

    def query_embed(self,texts):
        # Single-query batches bound peak memory. The indexed vectors stay unchanged.
        for text in texts:
            ids=np.array([self.token_ids(text)],dtype=np.int64)
            mask=np.ones_like(ids)
            inputs={'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)}
            output=self.session.run(None,{k:v for k,v in inputs.items() if k in self.inputs})[0]
            dtype=output.dtype
            if output.ndim==3:
                output=(output*mask[...,None]).sum(axis=1)/mask.sum(axis=1,keepdims=True)
            yield output[0].astype(dtype).astype(np.float32)
