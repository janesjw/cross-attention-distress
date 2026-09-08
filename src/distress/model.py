"""Reconstructed MMAN. The original executable implementation is unavailable."""
import torch
from torch import nn
from torch.nn import functional as F

VARIANTS=('sequence_cross_attention','manuscript_singleton','mean_fusion','gating_only','concat',
          'long_only','short_only','text_only','numerical_only')

class MMAN(nn.Module):
    def __init__(self,text_encoder=None,variant='sequence_cross_attention',d_model=128,settings=None):
        super().__init__()
        if variant not in VARIANTS: raise ValueError(variant)
        self.variant=variant;self.d=d_model
        c=dict(heads=4,annual_layers=2,annual_ff=2*d_model,annual_dropout=.2,
               short_layers=2,short_dropout=.3,classifier_dropout=.3,attention_dropout=0.)
        if settings is not None:c.update({k:v for k,v in settings.items() if k in c})
        self.use_long=variant not in ('short_only','text_only')
        self.use_short=variant not in ('long_only','text_only')
        self.use_text=variant not in ('long_only','short_only','numerical_only')
        self.cross=variant in ('sequence_cross_attention','manuscript_singleton','mean_fusion')
        if self.use_long:
            self.long_projection=nn.Linear(18,d_model)
            self.position=nn.Parameter(torch.empty(1,5,d_model));nn.init.normal_(self.position,std=.02)
            layer=nn.TransformerEncoderLayer(d_model,c['heads'],c['annual_ff'],c['annual_dropout'],activation='gelu',batch_first=True)
            self.long_encoder=nn.TransformerEncoder(layer,c['annual_layers'],enable_nested_tensor=False)
            # PyTorch clones identical initial layer values; initialize each layer independently.
            for layer in self.long_encoder.layers:
                nn.init.xavier_uniform_(layer.self_attn.in_proj_weight)
                for module in layer.modules():
                    if isinstance(module,nn.Linear):nn.init.xavier_uniform_(module.weight)
        if self.use_short:
            self.short_projection=nn.Linear(8,d_model)
            self.short_encoder=nn.LSTM(d_model,d_model,num_layers=c['short_layers'],dropout=c['short_dropout'],batch_first=True)
        if self.use_text:
            if text_encoder is None:raise ValueError('Text encoder required; no silent random-weight fallback')
            self.text_encoder=text_encoder
            self.text_projection=nn.Linear(text_encoder.config.hidden_size,d_model)
        if self.cross:
            self.paths=nn.ModuleList([nn.MultiheadAttention(d_model,c['heads'],dropout=c['attention_dropout'],batch_first=True) for _ in range(3)])
        n=6 if self.cross else (2 if variant=='numerical_only' else 3)
        if variant=='manuscript_singleton':
            self.global_gate=nn.Parameter(torch.zeros(6))
        elif variant in ('sequence_cross_attention','gating_only','numerical_only'):
            self.gate=nn.Sequential(nn.Linear(n*d_model,d_model),nn.GELU(),nn.Linear(d_model,n))
        elif variant=='concat':
            self.concat_projection=nn.Linear(3*d_model,d_model)
        self.classifier=nn.Sequential(nn.Linear(d_model,64),nn.GELU(),nn.BatchNorm1d(64),nn.Dropout(c['classifier_dropout']),
           nn.Linear(64,32),nn.GELU(),nn.BatchNorm1d(32),nn.Dropout(c['classifier_dropout']),nn.Linear(32,1))

    def forward(self,annual,quarterly,input_ids=None,attention_mask=None):
        vectors=[];attentions=[];gates=None
        if self.use_long:
            if annual.ndim!=3 or annual.shape[1:]!=(5,18):raise ValueError('annual shape must be [B,5,18]')
            long_tokens=self.long_encoder(self.long_projection(annual)+self.position)
            long=long_tokens[:,-1];vectors.append(long)
        if self.use_short:
            if quarterly.ndim!=3 or quarterly.shape[1:]!=(4,8):raise ValueError('quarterly shape must be [B,4,8]')
            short_tokens,_=self.short_encoder(self.short_projection(quarterly))
            short=short_tokens[:,-1];vectors.append(short)
        if self.use_text:
            if input_ids is None or attention_mask is None:raise ValueError('Explicit text IDs and padding mask required')
            if input_ids.shape!=attention_mask.shape or input_ids.shape[1]>512:raise ValueError('Invalid text shape')
            if not torch.all(attention_mask[:,0]==1):raise ValueError('CLS must be valid')
            text_tokens=self.text_projection(self.text_encoder(input_ids=input_ids,attention_mask=attention_mask).last_hidden_state)
            text=text_tokens[:,0];vectors.append(text)
        if self.cross:
            singleton=self.variant=='manuscript_singleton'
            text_keys=text[:,None] if singleton else text_tokens
            short_keys=short[:,None] if singleton else short_tokens
            mask=None if singleton else ~attention_mask.bool()
            for path,(query,keys,padding) in zip(self.paths,[(long,text_keys,mask),(short,text_keys,mask),(long,short_keys,None)]):
                out,weights=path(query[:,None],keys,keys,key_padding_mask=padding,need_weights=True,average_attn_weights=False)
                vectors.append(out[:,0]);attentions.append(weights)
        if self.variant.endswith('_only') and self.variant!='numerical_only':
            fused=vectors[0]
        elif self.variant=='concat':
            fused=self.concat_projection(torch.cat(vectors,dim=-1))
        else:
            stack=torch.stack(vectors,dim=1)
            if self.variant=='manuscript_singleton':gates=torch.softmax(self.global_gate,dim=0).expand(stack.shape[0],-1)
            elif self.variant=='mean_fusion':gates=stack.new_full(stack.shape[:2],1/len(vectors))
            else:gates=torch.softmax(self.gate(torch.cat(vectors,dim=-1)),dim=-1)
            fused=(stack*gates.unsqueeze(-1)).sum(dim=1)
        return {'logits':self.classifier(fused).squeeze(-1),'gates':gates,'attentions':attentions,'fused':fused}

def focal_loss(logits,targets,alpha=.75,gamma=2.):
    if not 0<=alpha<=1 or gamma<0:raise ValueError('Invalid focal loss parameters')
    targets=targets.to(logits.dtype)
    if not torch.all((targets==0)|(targets==1)):raise ValueError('Binary targets required')
    bce=F.binary_cross_entropy_with_logits(logits,targets,reduction='none')
    pt=torch.exp(-bce)
    weights=alpha*targets+(1-alpha)*(1-targets)
    return (weights*(1-pt).pow(gamma)*bce).mean()
