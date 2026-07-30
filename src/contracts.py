from __future__ import annotations
import hashlib,json,math
from collections.abc import Mapping
from dataclasses import fields,is_dataclass
from decimal import Decimal,ROUND_HALF_EVEN
from typing import Any

_METRICS={"artifact_count":0,"canonical_serializations":0,"sha256_calculations":0,"validated_copy_reuses":0,"authentic_checks":0}
_ARTIFACTS_BY_MEDIA:dict[str,int]={}

def reset_artifact_metrics()->None:
    for key in _METRICS:_METRICS[key]=0
    _ARTIFACTS_BY_MEDIA.clear()

def artifact_metrics()->dict[str,int]:
    return {**_METRICS,"artifacts_by_media":dict(sorted(_ARTIFACTS_BY_MEDIA.items()))}

class FrozenList(tuple):
    """Immutable list preserving list equality semantics."""
    __slots__=()
    def __new__(cls,items):return tuple.__new__(cls,items)
    def __repr__(self):return repr(list(self))
    def __eq__(self,other):
        return isinstance(other,(list,FrozenList)) and list(self)==list(other)
    def __ne__(self,other):return not self==other
    def __deepcopy__(self,memo):return self

class FrozenDict(dict):
    """Recursively immutable mapping used as an authenticated payload."""
    __slots__=()
    def __init__(self,items):dict.__init__(self,items)
    def _immutable(self,*args,**kwargs):raise TypeError("authenticated payload is immutable")
    __setitem__=__delitem__=clear=pop=popitem=setdefault=update=_immutable
    def __ior__(self,other):return self._immutable(other)
    def __deepcopy__(self,memo):return self

class _CanonicalState:
    __slots__=("digest","serialized")
    def __init__(self,digest_value:str,serialized:bytes|None=None):
        self.digest=digest_value;self.serialized=serialized

def _freeze(v:Any)->Any:
    if isinstance(v,FrozenDict) or isinstance(v,FrozenList):return v
    if is_dataclass(v) and not isinstance(v,type):
        return FrozenDict((field.name,_freeze(getattr(v,field.name))) for field in fields(v))
    if isinstance(v,Mapping):return FrozenDict((str(key),_freeze(value)) for key,value in v.items())
    if isinstance(v,list):return FrozenList(_freeze(value) for value in v)
    if isinstance(v,tuple):return tuple(_freeze(value) for value in v)
    if isinstance(v,set):return frozenset(_freeze(value) for value in v)
    return v

def _thaw(v:Any)->Any:
    if isinstance(v,FrozenDict):return {key:_thaw(value) for key,value in v.items()}
    if isinstance(v,FrozenList):return [_thaw(value) for value in v]
    if isinstance(v,tuple):return tuple(_thaw(value) for value in v)
    if isinstance(v,frozenset):return {_thaw(value) for value in v}
    return v

def _plain(v:Any)->Any:
    if isinstance(v,Artifact): return v.data
    if isinstance(v,Mapping): return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,FrozenList)): return [_plain(x) for x in v]
    if isinstance(v,Decimal):
        if not v.is_finite(): raise ValueError("non-finite number")
        q=v.quantize(Decimal('.000001'),rounding=ROUND_HALF_EVEN); return int(q) if q==q.to_integral() else float(q)
    if isinstance(v,float):
        if not math.isfinite(v): raise ValueError("non-finite number")
        q=Decimal(str(v)).quantize(Decimal('.000001'),rounding=ROUND_HALF_EVEN); return int(q) if q==q.to_integral() else float(q)
    return v

def _number(v:Any)->Any:
    if isinstance(v,Decimal):
        if not v.is_finite():raise ValueError("non-finite number")
        q=v.quantize(Decimal('.000001'),rounding=ROUND_HALF_EVEN);return int(q) if q==q.to_integral() else float(q)
    if isinstance(v,float):
        if not math.isfinite(v):raise ValueError("non-finite number")
        q=Decimal(str(v)).quantize(Decimal('.000001'),rounding=ROUND_HALF_EVEN);return int(q) if q==q.to_integral() else float(q)
    return v

def _canonical_chunks(v:Any):
    if isinstance(v,Artifact):v=v.payload
    if isinstance(v,Mapping):
        yield b"{"
        for index,key in enumerate(sorted(v,key=str)):
            if index:yield b","
            yield json.dumps(str(key),ensure_ascii=False,separators=(',',':')).encode()
            yield b":"
            yield from _canonical_chunks(v[key])
        yield b"}"
    elif isinstance(v,(list,tuple,FrozenList)):
        yield b"["
        for index,item in enumerate(v):
            if index:yield b","
            yield from _canonical_chunks(item)
        yield b"]"
    else:
        yield json.dumps(_number(v),ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()

def canonical_bytes(v:Any)->bytes:
    _METRICS["canonical_serializations"]+=1
    return b"".join(_canonical_chunks(v))
def digest(v:Any)->str:
    _METRICS["canonical_serializations"]+=1;_METRICS["sha256_calculations"]+=1
    result=hashlib.sha256()
    for chunk in _canonical_chunks(v):result.update(chunk)
    return result.hexdigest()

class Artifact(Mapping):
    def __setattr__(self,name,value):
        if hasattr(self,name):raise AttributeError(f"{name} is immutable")
        object.__setattr__(self,name,value)
    def __init__(self,data:Any,media_type:str,direct_input_sha256:str|None=None,source_hashes:Mapping[str,str]|None=None,validated=False):
        self._payload=_freeze(data);self.sha256=digest(self._payload)
        _METRICS["artifact_count"]+=1
        _ARTIFACTS_BY_MEDIA[media_type]=_ARTIFACTS_BY_MEDIA.get(media_type,0)+1
        self.media_type=media_type;self._canonical_state=_CanonicalState(self.sha256)
        self.direct_input_sha256=direct_input_sha256
        self.source_hashes=_freeze(dict(source_hashes or {}));self.validated=validated
    @classmethod
    def _shared(cls,source:"Artifact",validated:bool)->"Artifact":
        result=object.__new__(cls);result._payload=source._payload;result._canonical_state=source._canonical_state
        result.media_type=source.media_type;result.sha256=source.sha256;result.direct_input_sha256=source.direct_input_sha256
        result.source_hashes=source.source_hashes;result.validated=validated
        _METRICS["artifact_count"]+=1;_METRICS["validated_copy_reuses"]+=1
        _ARTIFACTS_BY_MEDIA[result.media_type]=_ARTIFACTS_BY_MEDIA.get(result.media_type,0)+1
        return result
    @property
    def data(self):return _thaw(self._payload)
    @property
    def payload(self)->Mapping[str,Any]:return self._payload
    def __getitem__(self,k):return _thaw(self._payload[k])
    def __iter__(self):return iter(self._payload)
    def __len__(self):return len(self._payload)
    def canonical_bytes(self):
        if self._canonical_state.serialized is None:
            self._canonical_state.serialized=canonical_bytes(self._payload)
        return self._canonical_state.serialized
    def authentic(self,media,schema=None):
        # _payload and _canonical_bytes are recursively immutable and were bound
        # by SHA-256 during construction. No mutable alias can change either.
        _METRICS["authentic_checks"]+=1
        return self.media_type==media and (schema is None or self._payload.get('schema_id')==schema)
    def validated_copy(self):return Artifact._shared(self,True)

class StageError(ValueError):
    def __init__(self,code,stage,refs=()):self.code=code;self.stage=stage;self.source_references=tuple(sorted(refs));super().__init__(code)
