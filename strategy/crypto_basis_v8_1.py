"""ALGOGENE V8.1 -- paired-exit correction to V8, not parameter optimization.
Select BTCUSD, BTCUSDM, ETHUSD, ETHUSDM; 60 min; USD 1,000,000;
leverage 1; short selling True; position netting False. Compare 2021-2025
with V8 using the same fee/risk-free settings (baseline 0).

UNCHANGED: prior168 midpoint basis observations; z>=2; executable opening
premium>=30bp and edge>=20bp over max(prior mean,0); equal coin quantities;
40% NAV gross/pair and 80% total; loss threshold75bp of initial spot-leg
notional; planned loss budget<=0.25% NAV/pair; max-hold EXIT REQUEST at72h;
6h cooldown; no funding curve or invented funding income.

CORRECTION: once a complete hedge exists, a normal pair exit is not submitted
until BOTH remaining symbols have fresh valid bid/ask quotes at the same
current timestamp. Both pending-close reservations are installed BEFORE
sending either order, so synchronous callbacks cannot break batch bookkeeping.
While a pair is CLOSING, new entries across the portfolio are paused. The
position and capital reservation remain until closure is confirmed.

This prevents the known V8 behavior of intentionally closing the fresh leg
while the other quote is stale. It CANNOT make two separate market orders
atomic. Explicit close rejects are retried on later fresh quotes; ambiguous
submission outcomes and unsupported partial fills halt new entries rather
than blindly duplicating orders. Unmatched/unconfirmed positions still need
manual reconciliation. A broken hedge caused by failed opening/closing fills
is unwound using available fresh quotes; a stale remaining leg can still
cause residual exposure. No automatic temporary re-hedge or exchange-native
spread order is assumed.

72h is a deadline to REQUEST exit, not a guaranteed flat deadline: during an
outage, V8.1 keeps a confirmed hedge intact and records the excess holding
and quote-wait duration instead of fabricating an executable price.
AUDIT V8.1 logs show active states, current net coin units, quote waiting and
observed unhedged duration. Intrahour timing is limited by the hourly feed.
The audit at Dec31 23:xx is a snapshot, not an engine stop callback. Standard
platform Summary may be a midnight snapshot; compare with fills and audits.

NO entry delay, commission model, synthetic bar fills or signal-threshold
changes are added in this baseline. Bid/ask is used, but extra commission,
funding, slippage and a next-hour execution stress test remain separate work.
For backtest research, not an unattended live trading system.
"""
from datetime import datetime, timedelta, timezone
from collections import deque, Counter
from math import floor, isfinite, sqrt
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest

GROUPS = {'BTC': ('BTCUSD', 'BTCUSDM'), 'ETH': ('ETHUSD', 'ETHUSDM')}
WINDOW = 168
MAX_WINDOW_HOURS = 210
RESET_GAP_HOURS = 6
ENTRY_Z = 2.0
MIN_ENTRY_BPS = 30.0
MIN_EDGE_BPS = 20.0
STD_FLOOR_BPS = 2.0
PAIR_GROSS_CAP = .40
TOTAL_GROSS_CAP = .80
PAIR_RISK_CAP = .0025
STOP_BPS = 75.0
MAX_HOLD_HOURS = 72
OPEN_TIMEOUT_HOURS = 2
COOLDOWN_HOURS = 6
VOLUME_SCALE = 10000
HOUR = timedelta(hours=1)


def stamp(value):
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def positive(value):
    try:
        x = float(value)
        return x if isfinite(x) and x > 0 else None
    except (ValueError, TypeError):
        return None


def get_quote(raw):
    if not isinstance(raw, dict):
        return None
    try:
        t = stamp(raw['timestamp'])
    except (KeyError, ValueError, TypeError, OverflowError):
        return None
    bid, ask = positive(raw.get('bidPrice')), positive(raw.get('askPrice'))
    if bid is None or ask is None or bid > ask:
        return None
    return {'t':t, 'bid':bid, 'ask':ask, 'mid':(bid+ask)/2}


def basis(s, f):
    # Common current spot-mid denominator: executable opening/closing spread.
    return {'mid':10000*(f['mid']-s['mid'])/s['mid'],
            'entry':10000*(f['bid']-s['ask'])/s['mid'],
            'exit':10000*(f['ask']-s['bid'])/s['mid']}


def entry_signal(observations, now, current):
    if len(observations) < WINDOW:
        return None
    if observations[-1][0] >= now:
        return None
    if now-observations[-1][0] > RESET_GAP_HOURS*HOUR:
        return None
    if now-observations[0][0] > MAX_WINDOW_HOURS*HOUR:
        return None
    xs = [x for t,x in observations]
    mean = sum(xs)/len(xs)
    sd = sqrt(sum((x-mean)**2 for x in xs)/len(xs))
    z = (current['mid']-mean)/max(sd,STD_FLOOR_BPS)
    target = max(mean,0.0)
    if z < ENTRY_Z or current['entry'] < MIN_ENTRY_BPS or current['entry']-target < MIN_EDGE_BPS:
        return None
    return {'mean':mean, 'sd':sd, 'z':z, 'target':target, **current}


class AlgoEvent:
    def __init__(self):
        self.contracts = {}
        self.history = {g:deque(maxlen=WINDOW) for g in GROUPS}
        self.last_sample = {}
        self.pairs = {}  # Keep DONE IDs for duplicate/late-fill matching.
        self.refs = {}
        self.seen_fills = set()
        self.cooldown = {}
        self.last_entry = {}
        self.now = None
        self.quotes = {}
        self.sequence = 0
        self.month = None
        self.counts = Counter()
        self.halt_entries = False
        self.warned = {}
        self.last_year_end_audit = None

    def log(self, *items):
        self.evt.consoleLog(*items)

    def warn(self, key, *items):
        day = self.now.date() if self.now is not None else None
        if self.warned.get(key) != day:
            self.warned[key] = day
            self.log(key, *items)

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self,mEvt)
        symbols = [s for pair in GROUPS.values() for s in pair]
        missing = set(symbols)-set(mEvt.get('subscribeList',[]))
        if missing:
            raise ValueError('Select all four instruments: '+', '.join(sorted(missing)))
        for symbol in symbols:
            spec = self.evt.getContractSpec(symbol)
            size = positive(spec.get('contractSize'))
            if size is None or abs(size-1)>1e-9:
                raise ValueError('V8.1 requires confirmed contractSize=1 for '+symbol)
            self.contracts[symbol] = size
            self.log('CONTRACT',symbol,spec)
        self.log('START V8.1 paired-exit correction | long spot + short perpetual | prior168 z2',
                 '| min premium30bp edge20bp | pair/total gross40%/80% | stop75bp of spot leg',
                 '| risk cap0.25% NAV/pair | request exit72h cooldown6h | no funding curve assigned | synchronized pair exits')
        self.evt.start()

    def active_pairs(self):
        return [p for p in self.pairs.values() if p['phase']!='DONE']

    def fresh(self, symbol):
        return symbol in self.quotes and self.quotes[symbol]['t']==self.now

    def gross_reserved(self):
        total = 0.0
        for p in self.active_pairs():
            marked = 0.0
            for leg in p['legs'].values():
                q = self.quotes.get(leg['symbol'])
                mark = q['mid'] if q else leg['estimate']
                qty = sum(lot['qty'] for lot in leg['lots'].values() if not lot['closed'])
                if leg['state'] in ('queued','pending','unknown'):
                    qty = max(qty,leg['requested'])
                marked += qty*mark
            total += max(p['reserved_gross'],marked)
        return total

    def open_pair(self, group, signal, nav, account):
        if self.halt_entries or self.closing_block() or any(p['group']==group for p in self.active_pairs()):
            return
        spot,future = GROUPS[group]
        s,f = self.quotes[spot],self.quotes[future]
        used = self.gross_reserved()
        budget = min(nav*PAIR_GROSS_CAP,max(0.0,nav*TOTAL_GROSS_CAP-used))
        available = positive(account.get('availableBalance'))
        if available is None:
            self.warn('NO_AVAILABLE_BALANCE','new pair skipped')
            return
        pending_reserved = sum(p['reserved_gross'] for p in self.active_pairs()
                               if p['phase']=='OPENING' or p['created']==self.now)
        budget = min(budget,max(0.0,.95*available-pending_reserved))
        qty = min(budget/(s['ask']+f['bid']),nav*PAIR_RISK_CAP/(s['ask']*STOP_BPS/10000))
        qty = floor(qty*VOLUME_SCALE)/VOLUME_SCALE
        if qty<=0:
            return
        self.sequence += 1
        pid = 'V8-'+group+'-'+str(self.sequence)
        p = {'id':pid,'group':group,'phase':'OPENING','created':self.now,
             'target':signal['target'],'entry_signal':dict(signal),
             'reserved_gross':qty*(s['ask']+f['bid']),
             'stop_usd':qty*s['ask']*STOP_BPS/10000,'reason':None,'legs':{},
             'was_hedged':False,'exit_wait_since':None,'exit_wait_hours':0.0,
             'unhedged_since':None,'unhedged_hours':0.0,'unhedged_max_hours':0.0}
        for key,symbol,side,estimate in (('S',spot,1,s['ask']),('F',future,-1,f['bid'])):
            ref = pid+'-'+key
            p['legs'][key] = {'symbol':symbol,'side':side,'requested':qty,'estimate':estimate,
                              'state':'queued','ref':ref,'lots':{}}
            self.refs[ref] = (pid,key)
        self.pairs[pid] = p  # Reserve BOTH legs before either callback can arrive.
        self.counts['pair_attempts'] += 1
        self.log('PAIR_OPEN',pid,self.now,'quantity_each',qty,'signal',signal,
                 'reserved_gross',p['reserved_gross'],'stop_USD',p['stop_usd'])
        for key in ('S','F'):
            if p['phase']!='OPENING':
                break
            leg = p['legs'][key]
            leg['state'] = 'pending'
            order = AlgoAPIUtil.OrderObject()
            order.instrument = leg['symbol']
            order.orderRef = leg['ref']
            order.openclose = 'open'
            order.buysell = leg['side']
            order.ordertype = 0
            order.volume = qty
            try:
                self.evt.sendOrder(order)
            except Exception as exc:
                # A send exception has an ambiguous submission outcome.
                if leg['state']=='pending':
                    leg['state']='unknown'
                self.halt_entries=True
                self.log('SEND_UNKNOWN',pid,key,repr(exc),'new entries halted; reservation retained')
                self.request_exit(p,'SEND_UNKNOWN')
        self.finish_if_flat(p)

    def request_exit(self,p,reason):
        if p['phase']!='CLOSING':
            p['phase']='CLOSING'
            p['reason']=reason
            self.log('PAIR_EXIT',p['id'],self.now,reason)
        for leg in p['legs'].values():
            if leg['state']=='queued':
                leg['state']='cancelled'  # Never submitted, not an exchange cancellation.
        self.try_closes(p)

    def closing_block(self):
        return any(p['phase']=='CLOSING' for p in self.active_pairs())

    def net_units(self,p):
        return sum(leg['side']*lot['qty'] for leg in p['legs'].values()
                   for lot in leg['lots'].values() if not lot['closed'])

    def audit_exposure(self,p):
        net=self.net_units(p)
        if abs(net)>1e-8:
            if p['unhedged_since'] is None:
                p['unhedged_since']=self.now
            duration=(self.now-p['unhedged_since']).total_seconds()/3600
            p['unhedged_max_hours']=max(p['unhedged_max_hours'],duration)
            if duration>0:
                self.warn('UNHEDGED_WAIT_'+p['id'],self.now,'net_coin_units',net,
                          'hours',duration,'state',p['phase'])
        elif p['unhedged_since'] is not None:
            duration=max(0.0,(self.now-p['unhedged_since']).total_seconds()/3600)
            p['unhedged_hours']+=duration
            p['unhedged_max_hours']=max(p['unhedged_max_hours'],duration)
            if duration>0:
                self.counts['unhedged_episodes']+=1
                self.counts['unhedged_hours_sum']+=duration
                self.counts['unhedged_hours_max']=max(self.counts['unhedged_hours_max'],duration)
                self.log('UNHEDGED_END',p['id'],self.now,'observed_hours',duration)
            p['unhedged_since']=None

    def close_wait_end(self,p):
        if p['exit_wait_since'] is not None:
            duration=max(0.0,(self.now-p['exit_wait_since']).total_seconds()/3600)
            p['exit_wait_hours']+=duration
            self.counts['paired_exit_quote_wait_hours']+=duration
            self.log('PAIRED_EXIT_QUOTES_READY',p['id'],self.now,'wait_hours',duration)
            p['exit_wait_since']=None

    def try_closes(self,p):
        remaining=[(leg,trade_id,lot) for leg in p['legs'].values()
                   for trade_id,lot in leg['lots'].items() if not lot['closed']]
        # For an intact confirmed hedge, never deliberately sell only its fresh
        # side during a quote outage. Failed/partial fills use recovery instead.
        both_sides=len(set(leg['side'] for leg,_,_ in remaining))==2
        equal_units=abs(self.net_units(p))<=1e-8
        pending=any(lot['pending_close'] for _,_,lot in remaining)
        if p['was_hedged'] and both_sides and equal_units and not pending:
            if not all(self.fresh(leg['symbol']) for leg,_,_ in remaining):
                if p['exit_wait_since'] is None:
                    p['exit_wait_since']=self.now
                    self.counts['paired_exit_quote_waits']+=1
                self.warn('PAIRED_EXIT_WAIT_'+p['id'],self.now,'keep both legs open',
                          'net_units',self.net_units(p),
                          'wait_hours',(self.now-p['exit_wait_since']).total_seconds()/3600)
                return
            self.close_wait_end(p)
        candidates=[(leg,trade_id,lot) for leg,trade_id,lot in remaining
                    if self.fresh(leg['symbol']) and not lot['pending_close']
                    and lot.get('last_close_try')!=self.now]
        # Reserve the entire batch first, before any synchronous fill callback.
        for leg,trade_id,lot in candidates:
            lot['pending_close']=True
            lot['close_submitted_at']=self.now
            lot['last_close_try']=self.now
        for leg,trade_id,lot in candidates:
            order=AlgoAPIUtil.OrderObject()
            order.instrument=leg['symbol']
            order.tradeID=trade_id
            order.orderRef=leg['ref']+'-C'
            order.openclose='close'
            try:
                self.evt.sendOrder(order)
            except Exception as exc:
                self.halt_entries=True
                self.log('CLOSE_SEND_UNKNOWN',p['id'],trade_id,repr(exc),
                         'new entries halted; close reservation retained')
        self.finish_if_flat(p)

    def audit_snapshot(self,trigger,nav=None):
        states=[]
        for p in self.active_pairs():
            self.audit_exposure(p)
            states.append({'pair':p['id'],'state':p['phase'],
                           'age_hours':(self.now-p['created']).total_seconds()/3600,
                           'net_coin_units':self.net_units(p),
                           'exit_quote_wait_hours':p['exit_wait_hours'] + (
                               (self.now-p['exit_wait_since']).total_seconds()/3600
                               if p['exit_wait_since'] is not None else 0.0),
                           'unhedged_hours':p['unhedged_hours'] + (
                               (self.now-p['unhedged_since']).total_seconds()/3600
                               if p['unhedged_since'] is not None else 0.0),
                           'pending_open':[(leg['symbol'],leg['state']) for leg in p['legs'].values()
                                           if leg['state'] in ('queued','pending','unknown')],
                           'pending_close':[tid for leg in p['legs'].values()
                                            for tid,lot in leg['lots'].items() if lot['pending_close']]})
        self.log('AUDIT V8.1',self.now,trigger,'NAV',nav,'counters',dict(self.counts),
                 'active',states,'halt_new_entries',self.halt_entries,
                 'closing_entry_block',self.closing_block())

    def finish_if_flat(self,p):
        unresolved = any(leg['state'] in ('queued','pending','unknown') for leg in p['legs'].values())
        lots = [lot for leg in p['legs'].values() for lot in leg['lots'].values()]
        if not unresolved and all(lot['closed'] for lot in lots) and p['phase']!='DONE':
            self.audit_exposure(p)
            self.close_wait_end(p)
            p['phase']='DONE'
            self.cooldown[p['group']]=self.now+COOLDOWN_HOURS*HOUR
            self.counts['pairs_done']+=1
            pnl=sum(lot.get('pnl',0.0) for lot in lots)
            self.log('PAIR_DONE',p['id'],self.now,p['reason'],'gross_PnL_before_costs',pnl,
                     'holding_hours',(self.now-p['created']).total_seconds()/3600,
                     'exit_quote_wait_hours',p['exit_wait_hours'],
                     'observed_unhedged_hours',p['unhedged_hours'],
                     'max_unhedged_hours',p['unhedged_max_hours'])

    def liquidation_pnl(self,p):
        pnl=0.0
        for leg in p['legs'].values():
            if not self.fresh(leg['symbol']):
                return None
            q=self.quotes[leg['symbol']]
            price=q['bid'] if leg['side']==1 else q['ask']
            for lot in leg['lots'].values():
                pnl += lot.get('pnl',0.0) if lot['closed'] else leg['side']*lot['qty']*(price-lot['price'])
        return pnl

    def on_bulkdatafeed(self,isSync,bd,ab):
        if not isinstance(bd,dict):
            return
        parsed={s:get_quote(bd.get(s)) for s in self.contracts}
        parsed={s:q for s,q in parsed.items() if q is not None}
        if not parsed:
            return
        now=max(q['t'] for q in parsed.values())
        if self.now is not None and now<self.now:
            return
        self.now=now
        self.quotes=parsed
        for p in list(self.active_pairs()):
            self.audit_exposure(p)
            for leg in p['legs'].values():
                for tid,lot in leg['lots'].items():
                    if lot['pending_close'] and now-lot.get('close_submitted_at',now)>=OPEN_TIMEOUT_HOURS*HOUR:
                        self.halt_entries=True
                        self.warn('CLOSE_PENDING_HALT_'+p['id'],now,tid,
                                  'ambiguous pending close; no duplicate submission')
            age=(now-p['created']).total_seconds()/3600
            if p['phase']=='CLOSING':
                self.try_closes(p)
                continue
            if p['phase']=='OPENING' and age>=OPEN_TIMEOUT_HOURS:
                self.request_exit(p,'OPEN_TIMEOUT_UNWIND')
                continue
            if p['phase']=='ACTIVE':
                if age>=MAX_HOLD_HOURS:
                    self.request_exit(p,'MAX_HOLD')
                    continue
                pnl=self.liquidation_pnl(p)
                if pnl is None:
                    self.warn('STALE_PAIR_'+p['group'],'paired exit decision waiting for fresh quotes')
                    continue
                spot,future=GROUPS[p['group']]
                closing=basis(parsed[spot],parsed[future])['exit']
                if pnl<=-p['stop_usd']:
                    self.request_exit(p,'PAIR_LOSS_STOP')
                elif closing<=p['target'] and pnl>0:
                    self.request_exit(p,'BASIS_CONVERGED')
        if not isSync:
            return
        nav=positive(ab.get('NAV')) if isinstance(ab,dict) else None
        month=now.strftime('%Y-%m')
        if month!=self.month:
            self.month=month
            self.audit_snapshot('MONTH',nav)
        for group,(spot,future) in GROUPS.items():
            if not self.fresh(spot) or not self.fresh(future):
                continue
            prior=self.last_sample.get(group)
            if prior is not None and now<=prior:
                continue
            obs=self.history[group]
            if prior is not None and now-prior>RESET_GAP_HOURS*HOUR:
                obs.clear()
                self.counts[group+'_window_resets']+=1
            current=basis(parsed[spot],parsed[future])
            signal=entry_signal(obs,now,current) # Compute BEFORE adding current.
            obs.append((now,current['mid']))
            self.last_sample[group]=now
            self.counts[group+'_samples']+=1
            aligned=len(parsed)==len(self.contracts) and all(q['t']==now for q in parsed.values())
            if signal is None or not aligned or nav is None or self.halt_entries or self.closing_block():
                continue
            if any(p['group']==group for p in self.active_pairs()):
                continue
            if self.cooldown.get(group) is not None and now<self.cooldown[group]:
                continue
            if self.last_entry.get(group)==now:
                continue
            self.last_entry[group]=now
            self.open_pair(group,signal,nav,ab)

        if now.month==12 and now.day==31 and now.hour==23 and self.last_year_end_audit!=now.year:
            self.last_year_end_audit=now.year
            self.audit_snapshot('YEAR_END_QUOTE',nav)

    def on_orderfeed(self,of):
        symbol=getattr(of,'instrument',None)
        kind=getattr(of,'openclose',None)
        status=str(getattr(of,'status','')).lower()
        ref=str(getattr(of,'orderRef','') or '')
        trade_id=getattr(of,'tradeID',None)
        found=None
        if kind=='open' and ref in self.refs:
            pid,key=self.refs[ref]
            found=(self.pairs[pid],self.pairs[pid]['legs'][key])
        elif kind=='close':
            for p in self.pairs.values():
                for leg in p['legs'].values():
                    if trade_id in leg['lots']:
                        found=(p,leg)
                        break
                if found is not None:
                    break
        elif kind=='open' and not ref:
            options=[(p,leg) for p in self.active_pairs() for leg in p['legs'].values()
                     if leg['symbol']==symbol and leg['state'] in ('pending','unknown')]
            if len(options)==1:
                found=options[0]
        if found is None:
            if status=='success' and kind=='open' and trade_id not in self.seen_fills:
                self.halt_entries=True
                self.log('UNMATCHED_FILL_HALT',symbol,trade_id,ref,'manual reconciliation required')
            return
        p,leg=found
        if symbol is not None and symbol!=leg['symbol']:
            self.halt_entries=True
            self.log('SYMBOL_MISMATCH_HALT',p['id'],symbol,leg['symbol'])
            return
        if status in ('reject','kill'):
            self.log('LEG_FAILED',p['id'],leg['symbol'],kind,status,getattr(of,'reason',''))
            if kind=='open':
                leg['state']='rejected'
                self.request_exit(p,'OPEN_REJECT_UNWIND')
            else:
                lot=leg['lots'][trade_id]
                lot['pending_close']=False
                # Retry only on a later quote; never an immediate rejection loop.
            return
        if status!='success':
            if 'partial' in status:
                self.halt_entries=True
                self.log('UNSUPPORTED_PARTIAL_STATUS',p['id'],symbol,status,'manual reconciliation required')
                self.request_exit(p,'PARTIAL_STATUS_UNWIND')
            return
        price=positive(getattr(of,'fill_price',None))
        qty=positive(getattr(of,'fill_volume',None))
        if price is None or qty is None or trade_id is None:
            self.halt_entries=True
            self.log('INVALID_FILL_HALT',p['id'],kind,trade_id,price,qty)
            self.request_exit(p,'INVALID_FILL_UNWIND')
            return
        if kind=='open':
            if trade_id in self.seen_fills:
                return
            self.seen_fills.add(trade_id)
            late=leg['state'] not in ('pending','unknown') or p['phase']!='OPENING'
            leg['lots'][trade_id]={'qty':qty,'price':price,'closed':False,'pending_close':False}
            leg['state']='filled'
            self.log('LEG_FILL',p['id'],symbol,trade_id,'volume',qty,'price',price)
            self.audit_exposure(p)
            if late and p['phase']=='DONE':
                self.halt_entries=True
            if late or abs(qty-leg['requested'])>1e-8:
                self.request_exit(p,'LATE_OR_SIZE_MISMATCH_UNWIND')
            elif all(x['state']=='filled' for x in p['legs'].values()):
                sizes=[sum(l['qty'] for l in x['lots'].values()) for x in p['legs'].values()]
                if abs(sizes[0]-sizes[1])>1e-8:
                    self.request_exit(p,'HEDGE_SIZE_MISMATCH')
                else:
                    p['phase']='ACTIVE'
                    p['was_hedged']=True
                    self.counts['pairs_active']+=1
                    self.log('PAIR_ACTIVE',p['id'],'equal_units',sizes[0],'target_bp',p['target'])
        else:
            lot=leg['lots'][trade_id]
            if lot['closed']:
                return
            if abs(qty-lot['qty'])>1e-8:
                self.halt_entries=True
                self.log('PARTIAL_CLOSE_HALT',p['id'],trade_id,'manual reconciliation required')
                return  # Keep the unresolved close reserved; do not resubmit blindly.
            lot['closed']=True
            lot['pending_close']=False
            lot['pnl']=leg['side']*qty*(price-lot['price'])
            self.log('LEG_CLOSED',p['id'],symbol,trade_id,'gross_PnL',lot['pnl'])
            self.audit_exposure(p)
            self.finish_if_flat(p)

    def on_marketdatafeed(self,md,ab):
        pass

    def on_openPositionfeed(self,op,oo,uo):
        pass

    def on_dailyPLfeed(self,pl):
        pass

    def on_newsdatafeed(self,nd):
        pass

    def on_weatherdatafeed(self,wd):
        pass

    def on_econsdatafeed(self,ed):
        pass

    def on_corpAnnouncement(self,ca):
        pass
