"""Conservative admission diagnostics; last-clear evidence is not write history."""
import struct
from position_write_evidence import assess_writes
from position_surface_scope import assess_scope
from position_color_replay import assess_color


def assess(row):
    state=row.get('render_state') or {}
    clear=state.get('last_clear')
    result={'ready_for_stateful_replay':False,'initial_contents':'unknown',
            'full_target_clear_candidate':False,'depth_clear_candidate':False,
            'stencil_clear_candidate':False,'write_coverage':assess_writes(row),'color_scope':assess_scope(row),'color_draw':assess_color(row),'reasons':[]}
    reasons=result['reasons']
    if clear is None:
        reasons.append('clear_evidence_unavailable');return result
    if clear['reset_epoch']!=row['timing']['reset_epoch']:
        reasons.append('clear_from_older_reset');return result
    if clear['target_id']!=state['target_id'] or clear['target_desc']!=row['target']:
        reasons.append('clear_targets_other_surface');return result
    viewport=struct.unpack('<4I2f',bytes.fromhex(clear['viewport']))
    if clear['rects'] or viewport[:4]!=(0,0,*row['target'][:2]) or clear['scissor_enable']!=0:
        reasons.append('full_surface_clear_not_established');return result
    if clear['flags']&~7 or clear['flags']==0:
        reasons.append('unsupported_clear_flags');return result
    result['full_target_clear_candidate']=bool(clear['flags']&1)
    depth_matches=state['depth_id']!=0 and clear['depth_id']==state['depth_id'] and state['depth_desc'][:2]==row['target'][:2]
    depth=struct.unpack('<f',struct.pack('<I',clear['depth_bits']))[0]
    result['depth_clear_candidate']=bool(depth_matches and clear['flags']&2 and 0<=depth<=1)
    result['stencil_clear_candidate']=bool(depth_matches and clear['flags']&4)
    if not result['full_target_clear_candidate']:reasons.append('target_color_not_cleared')
    if state['states']['z_enable'] and not result['depth_clear_candidate']:reasons.append('depth_initial_contents_unknown')
    if state['states']['stencil_enable'] and not result['stencil_clear_candidate']:reasons.append('stencil_initial_contents_unknown')
    # Sampling omits draws and other writes after this clear. Never promote the
    # candidate to known initial contents without complete ordered write evidence.
    reasons.append('intervening_surface_writes_not_proven_complete')
    return result
