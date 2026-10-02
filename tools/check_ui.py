#!/usr/bin/env python3
"""Check account editing in an isolated offscreen Quickshell instance."""
import datetime as dt, json, os, pathlib, shutil, subprocess, tempfile, time
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='usage-ui-qa-') as tmp:
 b=pathlib.Path(tmp); env=dict(os.environ, HOME=tmp,XDG_CONFIG_HOME=tmp+'/config',XDG_DATA_HOME=tmp+'/data',XDG_STATE_HOME=tmp+'/state',CODEX_HOME=tmp+'/codex',CLAUDE_CONFIG_DIR=tmp+'/claude',GROK_HOME=tmp+'/grok',PI_CODING_AGENT_DIR=tmp+'/pi',MUSE_HOME=tmp+'/muse',CURSOR_HOME=tmp+'/cursor',AI_USAGE_ROOT=str(root),AI_USAGE_DEMO='1',QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
 clock_file=b/'config/omarchy/shell.json';clock_file.parent.mkdir(parents=True)
 def clock_config(pattern):
  return json.dumps({'version':1,'bar':{'position':'top','layout':{'center':[{'id':'omarchy.clock','format':pattern}]}}})
 clock_file.write_text(clock_config('ddd d MMM h:mm AP'))
 pin_file=b/'config/omarchy/ai-usage/pinned-limit.json';pin_file.parent.mkdir(parents=True)
 pin_file.write_text(json.dumps({'provider':'codex','label':'Weekly (7-day)','title':'Weekly'}))
 usage_file=b/'state/omarchy/agents/usage/codex.json';usage_file.parent.mkdir(parents=True)
 reset_at=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).isoformat()
 usage={'id':'codex','name':'Codex limits','limits':[{'label':'Weekly (7-day)','percent':0.26,'resetsAt':reset_at}]}
 usage_file.write_text(json.dumps(usage))
 for provider,percent in [('claude',.51),('codex-second',.73)]:
  (usage_file.parent/(provider+'.json')).write_text(json.dumps({'id':provider,'name':provider,
      'limits':[{'label':'Weekly (7-day)','percent':percent,'resetsAt':reset_at}]}))
 shutil.copytree(root/'ui',b/'ui'); p=b/'ui/shell.qml'; q=p.read_text().replace('implicitWidth: 1200','implicitWidth: 1000').replace('implicitHeight: 900','implicitHeight: 640')
 q=q.replace('function quit(): void', '''function qaSplitSet(zero: string): void {
            var next=JSON.parse(JSON.stringify(root.data))
            function bucket(input, output, write, read, value) {
                return {input:input,output:output,cacheWrite:write,cacheRead:read,
                    tokens:input+output+write+read,freshTokens:input+output+write,cachedTokens:read,value:value,unpricedTokens:0,sessions:1,requests:1}
            }
            var a=bucket(100,50,25,200000000,10), c=bucket(200,0,0,20,2.34), empty=bucket(0,0,0,0,0)
            if (zero === "true") { a=empty; c=empty }
            if (zero === "cache-only") { a=bucket(0,0,0,200000000,10); c=empty }
            next.summary=Object.assign({},next.summary,bucket(a.input+c.input,a.output+c.output,a.cacheWrite+c.cacheWrite,a.cacheRead+c.cacheRead,a.value+c.value))
            next.previous=empty
            next.cards=[a,c].map((item,index) => Object.assign({},next.cards[index],item,{id:index ? "claude" : "codex",provider:index ? "claude" : "codex",name:index ? "QA Claude" : "QA Codex",shade:0,models:[],valueShare:null,monthlyPrice:null,quotaScope:"",tokensPerSession:item.tokens,valuePerSession:item.value,quota:{limits:[{label:"Session",percent:.26,resetsAt:""}]}}))
            next.cards.forEach(card => { card.valueShare=next.summary.value ? card.value/next.summary.value*100 : null })
            next.models=[Object.assign({name:"Cache heavy",provider:"codex",routes:[]},a),Object.assign({name:"More new",provider:"claude",routes:[]},c),Object.assign({name:"Zero",provider:"codex",routes:[]},empty)]
            var start=Math.floor(new Date().setMinutes(0,0,0)/1000)
            var label=Qt.formatDateTime(new Date(start*1000),"HH:mm")
            next.hourly=[{start:start-3600,label:Qt.formatDateTime(new Date((start-3600)*1000),"HH:mm"),title:"Previous local hour",total:empty,providers:{codex:empty,claude:empty},cards:{codex:empty,claude:empty}},
                {start:start,label:label,title:label+" local to now",total:next.summary,providers:{codex:a,claude:c},cards:{codex:a,claude:c}}]
            if (zero === "cache-only") next.hourly[1].title=label+" local (cache-only fixture)"
            next.hourlyUnplaced={total:empty}
            if (zero === "legacy") {
                function strip(item) { if (!item || typeof item !== "object") return; delete item.freshTokens; delete item.cachedTokens; Object.keys(item).forEach(key => strip(item[key])) }
                strip(next)
            }
            if (zero === "unknown") {
                next.hourly[1].total={tokens:200000395,value:12.34}
                next.hourly[1].providers={codex:{tokens:200000175},claude:{tokens:220}}
            }
            root.days=7; root.provider="all"; root.selection=({}); root.metric="tokens"; root.breakdown="models"
            root.providerDetailsOpen=true; root.data=next
        }
        function qaTexts(): string {
            var labels=[]
            function walk(item) { if (item.visible && typeof item.text === "string") labels.push(item.text); (item.children || []).forEach(walk) }
            walk(captureRoot); return JSON.stringify(labels)
        }
        function qaSplit(): string {
            function texts(item) { var out=[]; function walk(child) { if (typeof child.text === "string" && child.visible) out.push(child.text); (child.children || []).forEach(walk) }; walk(item); return out }
            var tableRows=tableColumn.children.filter(item => item.modelData && item.modelData.name).map(item => ({name:item.modelData.name,text:texts(item)}))
            return JSON.stringify({fresh:root.amount(root.data.summary),value:root.data.summary.value,total:root.data.summary.tokens,
                labels:JSON.parse(qaTexts()),models:root.breakdownItems.map(row => ({name:row.name,amount:root.amount(row)})),
                hour:hourlyView.amount(root.data.hourly[1].total),peak:hourlyView.peak,segments:hourlyView.segments(root.data.hourly[1]),top:hourlyView.topSources,
                quota:root.data.cards[0].quota.limits[0].percent,table:tableRows,hourText:texts(hourlyView),
                sources:sourceColumn.children.filter(item => item.modelData && item.modelData.name).map(item => ({name:item.modelData.name,text:texts(item)}))})
        }
        function qaCaptureContent(path: string): string { return String(scroll.contentChildren[0].grabToImage(image => image.saveToFile(path))) }
        function qaMetric(value: string): void { root.metric=value }
        function qaPulseScope(source: string, filter: string): string {
            var oldProvider=root.provider, oldSelection=root.selection, oldDays=root.days
            root.days=1; root.provider=source; root.selection=JSON.parse(filter)
            var result=JSON.stringify({live:root.liveTodayView(),fresh:root.pulseTokens(),cached:root.pulseTotal("cached"),total:root.pulseTotal("total")})
            root.provider=oldProvider; root.selection=oldSelection; root.days=oldDays
            return result
        }
        function qaClock(): string {
            var start=Math.floor(new Date(2026,8,24,21,0,0).getTime()/1000)
            var hour={start:start,label:"21:00",title:"21:00 EDT to 22:00 EDT"}
            return JSON.stringify({label:root.localClock(start),title:root.hourTitle(hour),row:hourlyView.hourLabel(hour)})
        }
        function qaPulse(): string { return JSON.stringify({live:root.liveTodayView(),tokens:root.pulseTokens(),displayed:pulseCounter.displayedTokens,status:root.pulseStatus()}) }
        function qaPulseReload(): void { pulseFile.reload() }
        function qaScan(quiet: string): string {
            if (quiet !== "") root.refresh(quiet === "true")
            return JSON.stringify({running:scan.running,loading:root.viewLoading,enabled:scroll.enabled,opacity:scroll.opacity})
        }
        function qaPin(): string {
            return JSON.stringify({visible:pinnedColumn.parent.visible,pins:root.pinnedLimits.map(pin => {
                var limit=root.pinnedWindow(pin)
                return {name:root.pinnedName(pin),label:pin.label,percent:limit ? limit.percent : null,
                    reset:limit ? root.pinnedResetText(limit.resetsAt) : ""}
            })})
        }
        function qaPinReload(): void { pinFile.reload() }
        function qaUnpin(): void { root.unpinLimit(root.pinnedLimits[0]) }
        function qaAdd(): void { root.openSettings(); root.settingsTab="accounts"; root.draftAccounts=[{id:"qa",label:"QA",directories:[{provider:"codex",path:"/tmp/qa/.codex"}]}] }
        function qaSourcePicker(): string {
            sourcePicker.popup.open()
            sourcePicker.currentIndex=1
            sourcePicker.activated(1)
            var selected=root.provider
            root.selection=({excludeSource:["codex","claude"],account:"qa"})
            sourcePicker.currentIndex=0
            sourcePicker.activated(0)
            var all={provider:root.provider,index:sourcePicker.currentIndex,label:sourcePicker.displayText,
                excluded:root.selection.excludeSource || [],account:root.selection.account}
            root.selection=({excludeSource:["codex","claude"],account:"qa"})
            sourcePicker.currentIndex=1
            sourcePicker.activated(1)
            var focused={provider:root.provider,excluded:root.selection.excludeSource || [],account:root.selection.account}
            root.selection=({})
            root.chooseSource("all")
            sourcePicker.popup.close()
            return JSON.stringify({selected:selected,all:all,focused:focused})
        }
        function qaWalletSet(remaining: string, funded: string): void {
            var next = JSON.parse(JSON.stringify(root.data))
            next.cards = [{id:"codex:qa",provider:"codex",name:"QA wallet",shade:0,
                tokens:0,sessions:0,value:0,valueShare:null,unpricedTokens:0,monthlyPrice:null,
                quotaScope:"",models:[],quota:{limits:[{label:"Session",percent:.26,resetsAt:""}],balance:{remaining:Number(remaining),funded:Number(funded)}}}]
            root.providerDetailsOpen = true
            root.data = next
        }
        function qaQuotaLabels(): string {
            var labels = []
            function walk(item) {
                if (typeof item.text === "string" && /^\\d+% (used|limit)$/.test(item.text)) labels.push(item.text)
                ;(item.children || []).forEach(walk)
            }
            walk(captureRoot)
            return JSON.stringify(labels)
        }
        function qaCaptureWallet(path: string): string {
            function walk(item) {
                if (item.wallet !== undefined && item.spent !== undefined) return item
                var kids = item.children || []
                for (var i=0; i<kids.length; i++) { var result=walk(kids[i]); if(result) return result }
                return null
            }
            var wallet=walk(captureRoot)
            return String(wallet.grabToImage(image => image.saveToFile(path)))
        }
        function qaWallet(): string {
            function walk(item) {
                if (item.wallet !== undefined && item.spent !== undefined) {
                    var track = item.children.filter(child => child.height === 4 && child.radius === 2)[0]
                    return {remaining:item.wallet.remaining, funded:item.wallet.funded,
                        visible:item.visible, meterVisible:track.visible,
                        fillRatio:track.children[0].width / track.width,
                        detail:item.children.filter(child => child.visible && typeof child.text === "string").map(child => child.text).join(" "),
                        color:String(track.children[0].color), urgent:String(root.colorFor("claude"))}
                }
                var kids = item.children || []
                for (var i=0; i<kids.length; i++) {
                    var result = walk(kids[i]); if (result) return result
                }
                return null
            }
            return JSON.stringify(walk(captureRoot))
        }
        function qaSave(): void { root.saveSettings() }
        function qaScroll(): void { settingsScroll.contentItem.contentY=0 }
        function qaClick(): void {
            function walk(item) {
                if (item.text === "Add folder" && item.clicked) { item.clicked(); return true }
                var kids=item.children || []
                for(var i=0;i<kids.length;i++) if(walk(kids[i])) return true
                return false
            }
            walk(captureRoot)
        }
        function qaFill(): void {
            function walk(item) {
                if (item.placeholderText === "Full agent home folder, e.g. /mnt/work/.codex" && item.text === "") { item.text="/tmp/qa-copy/.codex"; item.textEdited() }
                var kids=item.children || []
                for(var i=0;i<kids.length;i++) walk(kids[i])
            }
            walk(captureRoot)
        }
        function quit(): void''');p.write_text(q)
 proc=subprocess.Popen(['quickshell','-p',str(b/'ui'),'--no-color'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 def ipc(*args):
  r=subprocess.run(['quickshell','ipc','-p',str(b/'ui'),'--any-display','call','analytics',*args],env=env,capture_output=True,text=True)
  if r.returncode: raise RuntimeError(r.stderr+r.stdout)
  return r.stdout.strip()
 try:
  time.sleep(1.5)
  assert json.loads(ipc('qaClock'))=={'label':'9:00 PM','title':'9:00 PM EDT to 10:00 PM EDT','row':'9:00 PM'}
  replacement=clock_file.with_suffix('.next');replacement.write_text(clock_config('ddd d MMM HH:mm'));os.replace(replacement,clock_file)
  time.sleep(.5)
  assert json.loads(ipc('qaClock'))=={'label':'21:00','title':'21:00 EDT to 22:00 EDT','row':'21:00'}
  picker=json.loads(ipc('qaSourcePicker'))
  assert picker=={'selected':'codex',
                  'all':{'provider':'all','index':0,'label':'All sources','excluded':[],'account':'qa'},
                  'focused':{'provider':'codex','excluded':['claude'],'account':'qa'}},picker
  pinned=json.loads(ipc('qaPin'))
  assert pinned['visible'] and pinned['pins'][0]['name']=='ChatGPT Main' and pinned['pins'][0]['label']=='Weekly (7-day)' and pinned['pins'][0]['percent']==.26 and 'Resets in' in pinned['pins'][0]['reset'],pinned
  usage['limits'][0]['percent']=.42
  replacement=usage_file.with_suffix('.next');replacement.write_text(json.dumps(usage));os.replace(replacement,usage_file)
  time.sleep(.3)
  updated=json.loads(ipc('qaPin'))
  assert updated['pins'][0]['percent']==.42,updated
  def add_pin(provider):
   return subprocess.run(['python3',str(root/'collector.py'),'pin','--pin-provider',provider,
       '--pin-label','Weekly (7-day)','--pin-title','Weekly'],env=env,capture_output=True,text=True)
  assert add_pin('claude').returncode==0
  assert add_pin('codex-second').returncode==0
  assert add_pin('grok').returncode!=0
  ipc('qaPinReload');time.sleep(.4)
  three=json.loads(ipc('qaPin'))
  assert [p['percent'] for p in three['pins']]==[.42,.51,.73],three
  ipc('qaUnpin');time.sleep(.4)
  unpinned=json.loads(ipc('qaPin'))
  assert unpinned['visible'] and [p['percent'] for p in unpinned['pins']]==[.51,.73],unpinned
  assert len(json.loads(pin_file.read_text())['pins'])==2
  now=dt.datetime.now().astimezone()
  pulse_file=b/'state/omarchy/ai-usage/hourly-summary.json';pulse_file.parent.mkdir(parents=True,exist_ok=True)
  pulse={'schemaVersion':2,'date':str(now.date()),'generatedAt':now.timestamp(),
         'utcOffsetMinutes':int((now.utcoffset() or dt.timedelta()).total_seconds()//60),'providers':{'codex':{'tokens':200000120,'freshTokens':120,'cachedTokens':200000000}},
         'hours':[],'unplacedTokens':0}
  pulse_file.write_text(json.dumps(pulse));ipc('qaPulseReload');time.sleep(.3)
  first=json.loads(ipc('qaPulse'))
  assert first['live'] and first['tokens']==120 and first['displayed']==120,first
  pulse['providers']['codex'].update(tokens=200000240,freshTokens=240)
  replacement=pulse_file.with_suffix('.next');replacement.write_text(json.dumps(pulse));os.replace(replacement,pulse_file)
  time.sleep(.3)
  moving=json.loads(ipc('qaPulse'))
  assert moving['tokens']==240 and 120 < moving['displayed'] < 240,moving
  time.sleep(1.2)
  settled=json.loads(ipc('qaPulse'))
  assert settled['displayed']==240,settled
  assert json.loads(ipc('qaPulseScope','codex','{}'))=={'live':True,'fresh':240,'cached':200000000,'total':200000240}
  assert json.loads(ipc('qaPulseScope','claude','{}'))=={'live':True,'fresh':0,'cached':0,'total':0}
  for selection in [{'account':'qa'},{'model':'gpt-6-sol'},{'excludeSource':['codex']},{'hourStart':100000}]:
   scoped=json.loads(ipc('qaPulseScope','all',json.dumps(selection)))
   assert scoped=={'live':False,'fresh':0,'cached':0,'total':0},scoped
  print('Live pulse honors source, account, model, excluded-source and hour scope')
  def scan_state(quiet=''):
   return json.loads(ipc('qaScan',quiet))
  for _ in range(50):
   if not scan_state()['running']:break
   time.sleep(.1)
  background=scan_state('true')
  assert background=={'running':True,'loading':False,'enabled':True,'opacity':1},background
  navigation=scan_state('false')
  assert navigation['running'] and navigation['loading'] and not navigation['enabled'],navigation
  for _ in range(50):
   done=scan_state()
   if not done['running']:break
   time.sleep(.1)
  time.sleep(.3)
  done=scan_state()
  assert done=={'running':False,'loading':False,'enabled':True,'opacity':1},done
  ipc('qaSplitSet','false');time.sleep(.3)
  split=json.loads(ipc('qaSplit'))
  assert split['fresh']==375 and split['total']==200000395 and split['value']==12.34 and split['quota']==.26,split
  assert split['hour']==375 and split['peak']==375,split
  assert split['models']==[{'name':'More new','amount':200},{'name':'Cache heavy','amount':175},{'name':'Zero','amount':0}],split
  assert split['top']==['claude','codex'] and sum(row['tokens'] for row in split['segments'])==375,split
  assert 'NEW TOKENS' in split['labels'] and 'CACHE REUSED' in split['labels'],split
  assert '375' in split['labels'] and '200.0M' in split['labels'] and '$12.34' in split['labels'],split
  assert any('Cache reused 200.0M' in text for text in split['labels']),split
  assert any('Total including cache' in text for text in split['labels']),split
  assert split['table'][1]['name']=='Cache heavy' and split['table'][1]['text']==['Cache heavy','175','$10.00','200.0M'],split['table']
  assert '375 new' in split['hourText'] and '200,000,020 cache' in split['hourText'],split['hourText']
  assert split['sources'][1]['text']==['QA Codex','26% used','175','200.0M','$10.00'],split['sources']
  print('Rendered dashboard cache split:',{k:v for k,v in split.items() if k!='labels'})
  ipc('qaMetric','value');time.sleep(.1)
  value_view=json.loads(ipc('qaSplit'))
  assert value_view['fresh']==value_view['hour']==12.34 and '$12.34' in value_view['hourText'] and value_view['quota']==.26,value_view
  ipc('qaMetric','tokens');time.sleep(.1)
  print('API-value hourly view unchanged: $12.34; quota unchanged: 26% used')
  if os.environ.get('USAGE_QA_CAPTURE_CONTENT'):
   image=pathlib.Path(os.environ['USAGE_QA_CAPTURE_CONTENT']).resolve();image.parent.mkdir(parents=True,exist_ok=True)
   image.unlink(missing_ok=True)
   assert ipc('qaCaptureContent',str(image))=='true'
   for _ in range(30):
    if image.exists():break
    time.sleep(.1)
   assert image.exists(),image
   print('Captured complete analytics content:',image)
  ipc('qaSplitSet','legacy');time.sleep(.2)
  legacy=json.loads(ipc('qaSplit'))
  assert legacy['fresh']==375 and legacy['hour']==375 and legacy['table']==split['table'],legacy
  print('Legacy report cacheRead fallback passed')
  ipc('qaSplitSet','unknown');time.sleep(.2)
  unknown=json.loads(ipc('qaSplit'))
  assert unknown['hour']==0 and 'Waiting for updated cache split' in unknown['hourText'] and '— new' in unknown['hourText'],unknown
  print('Inclusive-only legacy hourly graph safely withheld')
  ipc('qaSplitSet','cache-only');time.sleep(.2)
  cache_only=json.loads(ipc('qaSplit'))
  assert cache_only['fresh']==cache_only['hour']==0 and cache_only['total']==200000000 and cache_only['value']==10,cache_only
  assert '0 new' in cache_only['hourText'] and '200,000,000 cache' in cache_only['hourText'] and cache_only['segments']==[],cache_only
  print('Cache-only hour remains visible without a new-token bar')
  ipc('qaSplitSet','true');time.sleep(.2)
  zero=json.loads(ipc('qaSplit'))
  assert zero['fresh']==zero['hour']==zero['total']==zero['value']==0 and zero['peak']==1 and zero['quota']==.26,zero
  assert zero['segments']==[],zero
  print('Rendered zero-token dashboard:',{k:v for k,v in zero.items() if k!='labels'})
  for remaining,funded,expected,alarming in [(100,100,0,False),(74,100,.26,False),(10,100,.9,True),(0,100,1,True),(120,100,0,False),(74,0,0,False)]:
   ipc('qaWalletSet',str(remaining),str(funded));time.sleep(.15)
   quota_labels=json.loads(ipc('qaQuotaLabels'))
   assert quota_labels and all(label.endswith('% used') for label in quota_labels),quota_labels
   wallet=json.loads(ipc('qaWallet'))
   assert abs(wallet['fillRatio']-expected)<1e-9,wallet
   assert wallet['meterVisible']==(funded>0),wallet
   assert wallet['visible'],wallet
   assert (wallet['color']==wallet['urgent'])==alarming,wallet
   if funded>0:
    assert str(round(expected*100))+'% used' in wallet['detail'],wallet
   else:
    assert '%' not in wallet['detail'],wallet
   print('Rendered analytics wallet:',wallet)
   if remaining==74 and funded==100 and os.environ.get('USAGE_QA_CAPTURE_WALLET'):
    image=pathlib.Path(os.environ['USAGE_QA_CAPTURE_WALLET']).resolve();image.parent.mkdir(parents=True,exist_ok=True)
    assert ipc('qaCaptureWallet',str(image))=='true'
    for _ in range(30):
     if image.exists():break
     time.sleep(.1)
    assert image.exists(),image
    print('Captured real analytics wallet:',image)
  ipc('qaAdd');time.sleep(.4);ipc('qaClick');time.sleep(.3);ipc('qaFill');ipc('qaScroll');time.sleep(.3);ipc('capture',str(b/'account-editor.png'));time.sleep(.3);ipc('qaSave');time.sleep(1)
  settings=json.loads((b/'config/omarchy/ai-usage/settings.json').read_text())
  assert settings['accounts'][0]['directories']==[{'provider':'codex','path':'/tmp/qa/.codex'},{'provider':'codex','path':'/tmp/qa-copy/.codex'}],settings
  print('QML cache-split dashboard/model/hour rendering, legacy fallback, clock, source picker, three pinned limits and individual unpin, live pulse, quiet background refresh, account editor, and USED wallet meter passed at 1000x640')
 finally:
  proc.terminate();out=proc.communicate(timeout=5)[0]
  if any(e in out for e in ['ReferenceError','TypeError','Unable to assign','Failed to load']):raise RuntimeError(out)
