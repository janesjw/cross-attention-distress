"""Train-only preprocessing; labels are never imputed."""
import re
import numpy as np

class FinancialPreprocessor:
    def fit(self,x,industries):
        x=np.asarray(x,dtype=float)
        if x.ndim!=3 or len(x)!=len(industries):raise ValueError('Expected [firms,time,features]')
        if np.isinf(x).any():raise ValueError('Infinity is not a valid feature')
        flat=x.reshape(-1,x.shape[-1])
        if np.isnan(flat).all(axis=0).any():raise ValueError('A feature is entirely missing in training')
        self.low=np.nanquantile(flat,.01,axis=0);self.high=np.nanquantile(flat,.99,axis=0)
        clipped=np.clip(x,self.low,self.high)
        self.median=np.nanmedian(clipped.reshape(-1,x.shape[-1]),axis=0)
        self.by_industry={}
        for industry in sorted(set(industries)):
            rows=clipped[np.array(industries)==industry].reshape(-1,x.shape[-1])
            med=[]
            for j in range(x.shape[-1]):
                valid=rows[:,j][~np.isnan(rows[:,j])]
                med.append(np.median(valid) if len(valid) else self.median[j])
            self.by_industry[industry]=np.array(med)
        filled=self._impute(clipped,industries)
        self.mean=filled.mean(axis=(0,1));self.std=filled.std(axis=(0,1))
        self.std[self.std==0]=1
        return self

    def _impute(self,x,industries):
        return np.stack([np.where(np.isnan(row),self.by_industry.get(industry,self.median),row) for row,industry in zip(x,industries)])

    def transform(self,x,industries):
        x=np.asarray(x,dtype=float)
        if len(x)!=len(industries) or np.isinf(x).any():raise ValueError('Invalid features')
        missing=np.isnan(x)
        return ((self._impute(np.clip(x,self.low,self.high),industries)-self.mean)/self.std).astype('float32'),missing

    def to_dict(self):
        return {k:({i:v.tolist() for i,v in x.items()} if isinstance(x,dict) else x.tolist()) for k,x in vars(self).items()}

    @classmethod
    def from_dict(cls,data):
        obj=cls()
        for k,x in data.items():setattr(obj,k,({i:np.array(v) for i,v in x.items()} if isinstance(x,dict) else np.array(x)))
        return obj

def encode_disclosure(tokenizer,sections,max_length=512):
    """Ordered MD&A then board sections. Complete-sentence prefix; never cut a sentence."""
    if max_length>512:raise ValueError('Manuscript maximum is 512')
    budget=max_length-tokenizer.num_special_tokens_to_add(pair=False)
    content=[];seen=set();dropped_short=0;retained=0;truncated=False
    for sentence in re.split(r'(?<=[。！？!?；;])', ''.join(sections)):
        sentence=re.sub(r'\s+','',sentence)
        if len(sentence)<10:dropped_short+=1;continue
        if sentence in seen:continue
        ids=tokenizer.encode(sentence,add_special_tokens=False)
        if len(content)+len(ids)>budget:truncated=True;break
        content.extend(ids);seen.add(sentence);retained+=1
    if not content:raise ValueError('No complete eligible sentence fits; review extraction, do not silently feed empty text')
    ids=tokenizer.build_inputs_with_special_tokens(content)
    padding=max_length-len(ids)
    return {'input_ids':ids+[tokenizer.pad_token_id]*padding,'attention_mask':[1]*len(ids)+[0]*padding,
       'audit':{'content_tokens':len(content),'retained_sentences':retained,'dropped_short':dropped_short,'truncated':truncated}}
