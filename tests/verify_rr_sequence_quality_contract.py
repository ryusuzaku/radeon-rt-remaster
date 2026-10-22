"""Controls for reveal-age propagation and failure-sensitive error gates."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rr_sequence_quality import advance_ages,history_metrics,history_gates
from rr_reference import PIXELS


def need(ok,message):
    if not ok: raise AssertionError(message)


def main():
    previous=np.full(PIXELS,-1,dtype=np.int8)
    mapping=np.arange(PIXELS,dtype=np.int32); masks=np.zeros((4,PIXELS),dtype=bool)
    masks[1,10]=True
    first=advance_ages(previous,masks,mapping,False)
    need(first[10]==0 and np.count_nonzero(first>=0)==1,'reveal did not start cohort')
    masks[:]=False; masks[0,20:23]=True; mapping[20:22]=10
    second=advance_ages(first,masks,mapping,False)
    need(np.array_equal(second[20:23],[1,1,-1]),'mapping/duplicate/stable controls failed')
    masks[:]=False; masks[2,20]=True; masks[3,21]=True
    need(np.all(advance_ages(second,masks,mapping,False)==-1),'offscreen/unmatched retained cohort')
    masks[:]=False
    need(np.all(advance_ages(second,masks,mapping,True)==-1),'reset retained cohort')
    zero=np.zeros((PIXELS,3)); raw=zero.copy(); raw[20:22]=.5
    identity=history_metrics(raw,zero,zero,zero,second)
    need(identity[1]['rr_mse']==0 and identity[1]['raw_mse']==.25,'identity/error control')
    trail=zero.copy(); trail[20:22]=.25
    measured=history_metrics(zero,trail,zero,zero,second)
    need(measured[1]['rr_mse']==.0625,'persistent trail not detected')
    need(history_gates([dict(ages=measured)])['post_reveal_non_regression'] is False,'regression hidden')
    need(all(v is None for v in history_gates([]).values()),'missing coverage passed')
    noisy=history_metrics(raw,zero,zero,np.full_like(zero,.01),second)
    need(history_gates([dict(ages=noisy)])['post_reveal_reference_noise_small'] is False,'reference noise hidden')
    rejected=0
    invalid=[]
    bad=masks.copy(); bad[0,0]=True; bad[1,0]=True; invalid.append((previous,bad,mapping,False))
    bad=mapping.copy(); bad[0]=PIXELS; invalid.append((previous,masks,bad,False))
    invalid.append((previous,masks,mapping,1))
    invalid.append((previous,masks[:3],mapping,False))
    bad=masks.copy(); bad[1,0]=True; invalid.append((previous,bad,mapping,True))
    bad=previous.copy(); bad[0]=7; visible=masks.copy(); visible[0,0]=True
    invalid.append((bad,visible,np.arange(PIXELS,dtype=np.int32),False))
    for values in invalid:
        try: advance_ages(*values)
        except ValueError: rejected+=1
        else: raise AssertionError('malformed age input accepted')
    print(f'RR reveal history contract passes; {rejected} malformed inputs rejected')


if __name__=='__main__': main()
