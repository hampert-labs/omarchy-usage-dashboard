#!/usr/bin/env python3
"""Exercise the real panel's model summary without opening a desktop window."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--capture-source', type=Path, help='save an offscreen source picker image')
parser.add_argument('--capture-header', type=Path, help='save the offscreen panel header image')
parser.add_argument('--capture-content', type=Path, help='save the complete offscreen panel content')
parser.add_argument('--capture-viewport', type=Path, help='save the constrained offscreen panel viewport')
parser.add_argument('--theme', choices=['dark', 'light'], default='dark')
parser.add_argument('--panel-width', type=int, default=460)
parser.add_argument('--panel-height', type=int, default=360)
args = parser.parse_args()
omarchy_ui = Path('/usr/share/omarchy/shell/Ui')
omarchy_commons = Path('/usr/share/omarchy/shell/Commons')
if not omarchy_ui.exists() or not omarchy_commons.exists():
    raise SystemExit('This check needs the installed Omarchy shell')

with tempfile.TemporaryDirectory(prefix='.panel-qa-', dir=repo) as temp:
    root = Path(temp)
    (root / 'Commons').symlink_to(omarchy_commons)
    ui = root / 'Ui'
    ui.mkdir()
    for source in omarchy_ui.iterdir():
        if source.name != 'KeyboardPanel.qml':
            (ui / source.name).symlink_to(source)
    # The compositor-backed popup cannot load on Qt's offscreen platform.
    # Keep the panel content and model calculation, with only that host stubbed.
    (ui / 'KeyboardPanel.qml').write_text('''import QtQuick
Item {
  property Item anchorItem
  property var owner
  property var bar
  property bool open: false
  property Item focusTarget
  property int contentWidth: 460
  property int contentHeight: 900
  function fittedContentWidth(value) { return Math.min(value, PANEL_WIDTH) }
  function fittedContentHeight(value, maximum) { return Math.min(value, maximum, PANEL_HEIGHT) }
  width: contentWidth
  height: contentHeight
}
'''.replace('PANEL_WIDTH', str(args.panel_width)).replace('PANEL_HEIGHT', str(args.panel_height)))
    shutil.copytree(repo / 'plugin', root / 'plugin')
    panel_file = root / 'plugin/Panel.qml'
    panel_file.write_text(panel_file.read_text().replace(
        '  function modelTooltip(row) {',
        '  function qaSourcePicker() { return {label: providerSwitch.label, value: providerSwitch.value, text: providerSwitch.currentLabel()} }\n'
        '  function qaHeader() { return {pickerX: providerSwitch.mapToItem(column, 0, 0).x, pickerY: providerSwitch.mapToItem(column, 0, 0).y, pickerWidth: providerSwitch.width, buttonX: analyticsButton.mapToItem(column, 0, 0).x, buttonY: analyticsButton.mapToItem(column, 0, 0).y, buttonWidth: analyticsButton.width, columnWidth: column.width, pinnedY: pinnedSection.y} }\n'
        '  function qaCaptureSource(path) { return providerSwitch.grabToImage(function(image) { image.saveToFile(path) }) }\n\n'
        '  function qaCaptureHeader(path) { return headerControls.grabToImage(function(image) { image.saveToFile(path) }) }\n\n'
        '  function qaCaptureContent(path) { return column.grabToImage(function(image) { image.saveToFile(path) }) }\n'
        '  function qaCaptureViewport(path) { return keyCatcher.grabToImage(function(image) { image.saveToFile(path) }) }\n'
        '  function qaModels() { return modelSection.children.filter(item => item.row !== undefined).map(item => ({fresh: item.row.fresh, cached: item.row.cacheRead, total: item.row.total, share: item.share, text: item.children.filter(child => typeof child.text === "string").map(child => child.text)})) }\n'
        '  function qaHours() { var labels=[]; function walk(item) { if (typeof item.text === "string" && item.visible) labels.push(item.text); (item.children || []).forEach(walk) } walk(hourlySection); return {available: hourlyAvailable(), fresh: hourlyTotal("freshTokens"), cached: hourlyTotal("cachedTokens"), total: hourlyTotal("tokens"), rows: hourRows(), labels: labels} }\n'
        '  function qaScrollState() { return {contentY: panelFlick.contentY, contentHeight: panelFlick.contentHeight, height: panelFlick.height, size: panelScroll.size, position: panelScroll.position, width: panelScroll.width, visible: panelScroll.visible, outsideClip: panelScroll.parent === keyCatcher} }\n'
        '  function qaScrollDown() { panelScroll.increase(); return qaScrollState() }\n\n'
        '  function qaScrollBar() { return panelScroll }\n'
        '  function qaResetScroll() { panelFlick.contentY = 0 }\n\n'
        '  function qaBalance() { var meter = balanceSection.children.filter(item => item.value !== undefined)[0]; return {ratio: balanceSection.ratio, alarming: root.balanceAlarming, meterValue: meter.value, meterVisible: meter.visible, fillRatio: meter.children[1].width / meter.width, color: String(meter.children[1].color), urgent: String(root.urgent), detail: root.balanceDetailText(root.balance), balance: balanceValue.text} }\n'
        '  function qaPercentLabels() { var labels = []; function walk(item) { if (typeof item.text === "string" && /^\\d+%/.test(item.text)) labels.push(item.text); (item.children || []).forEach(walk) } walk(root); return labels }\n'
        '  function modelTooltip(row) {'))
    (root / 'shell.qml').write_text('''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import "plugin" as Plugin
ShellRoot {
  Window {
    width: 600
    height: 900
    visible: true
    color: "#151b18"
    Plugin.Panel { id: panel; width: 460; height: 20 }
  }
  // Keep the QtTest pointer helper available for IPC without auto-running a test suite.
  TestCase { id: dragDriver; name: "PanelScrollDrag"; when: false }
  IpcHandler {
    target: "panelqa"
    function inspect(): string {
      return JSON.stringify(panel.models.map(row => ({name: row.name, total: row.total, fresh: row.fresh, cached: row.cacheRead,
        details: panel.modelTooltip(row)})))
    }
    function percentLabels(): string { return JSON.stringify(panel.qaPercentLabels()) }
    function wallet(): string { return JSON.stringify(panel.qaBalance()) }
    function watchLimits(): string { return JSON.stringify(panel.allLimitRows()) }
    function source(): string { return JSON.stringify(panel.qaSourcePicker()) }
    function header(): string { return JSON.stringify(panel.qaHeader()) }
    function selectCodex(): void { panel.selectedProviderId = "codex" }
    function captureSource(path: string): string { return String(panel.qaCaptureSource(path)) }
    function captureHeader(path: string): string { return String(panel.qaCaptureHeader(path)) }
    function captureContent(path: string): string { return String(panel.qaCaptureContent(path)) }
    function captureViewport(path: string): string { return String(panel.qaCaptureViewport(path)) }
    function renderedModels(): string { return JSON.stringify(panel.qaModels()) }
    function hours(): string { return JSON.stringify(panel.qaHours()) }
    function scrollState(): string { return JSON.stringify(panel.qaScrollState()) }
    function scrollDown(): string { return JSON.stringify(panel.qaScrollDown()) }
    function dragScroll(): string {
      panel.qaResetScroll()
      var scroll = panel.qaScrollBar()
      dragDriver.mouseDrag(scroll, scroll.width / 2, Math.max(8, scroll.size * scroll.height / 2), 0, 120)
      return JSON.stringify(panel.qaScrollState())
    }
  }
}
''')
    usage = root / 'state/omarchy/agents/usage'
    usage.mkdir(parents=True)
    reset_at = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).isoformat()
    now = dt.datetime.now().astimezone()
    hourly_file = root / 'state/omarchy/ai-usage/hourly-summary.json'
    hourly_file.parent.mkdir(parents=True, exist_ok=True)
    hourly = {'schemaVersion': 2, 'date': str(now.date()), 'generatedAt': now.timestamp(),
              'utcOffsetMinutes': int((now.utcoffset() or dt.timedelta()).total_seconds() // 60),
              'availableProviders': ['codex', 'claude'],
              'providers': {'codex': {'tokens': 200000175, 'freshTokens': 175, 'cachedTokens': 200000000},
                            'claude': {'tokens': 220, 'freshTokens': 200, 'cachedTokens': 20}},
              'hours': [{'start': int(now.replace(minute=0, second=0, microsecond=0).timestamp()), 'label': now.strftime('%H:00'),
                         'providers': {'codex': 200000175, 'claude': 220},
                         'freshProviders': {'codex': 175, 'claude': 200}, 'cachedProviders': {'codex': 200000000, 'claude': 20}}]}
    hourly_file.write_text(json.dumps(hourly))
    (usage / 'codex.json').write_text(json.dumps({
        'id': 'codex', 'name': 'Codex', 'activeDays': 1,
        'limits': [{'label': 'Weekly (7-day)', 'percent': 0.26, 'resetsAt': reset_at}],
        'modelUsage': {'gpt-6-sol': {'inputTokens': 100, 'outputTokens': 50,
                                     'cacheReadInputTokens': 200000000, 'cacheCreationInputTokens': 25},
                       'gpt-zero': {'inputTokens': 0, 'outputTokens': 0, 'cacheReadInputTokens': 0}},
    }))
    (usage / 'claude.json').write_text(json.dumps({
        'id': 'claude', 'name': 'Claude', 'activeDays': 1,
        'limits': [
            {'label': 'Session', 'title': 'Session', 'percent': 1, 'resetsAt': reset_at},
            {'label': 'Weekly (7-day)', 'title': 'Weekly', 'percent': 0.97, 'resetsAt': reset_at},
            {'label': 'Model weekly', 'title': 'Weekly', 'percent': 0.98, 'resetsAt': reset_at},
            {'label': 'Monthly', 'title': 'Monthly', 'percent': 0.59},
            {'label': 'Expired', 'percent': 1, 'resetsAt': '2020-01-01T00:00:00Z'},
        ],
        'modelUsage': {'claude-sonnet-4': {'inputTokens': 200, 'cacheReadInputTokens': 20}},
    }))
    pins = root / 'config/omarchy/ai-usage/pinned-limit.json'
    pins.parent.mkdir(parents=True)
    pins.write_text(json.dumps({'pins': [{'provider': 'codex', 'label': 'Weekly (7-day)', 'title': 'Weekly'},
        {'provider': 'claude', 'label': 'Session', 'title': 'Session'}]}))
    theme = root / '.local/state/omarchy/current/theme/colors.toml'
    theme.parent.mkdir(parents=True)
    theme.write_text('background = "#151b18"\nforeground = "#e8e6da"\naccent = "#7aaf92"\n'
                     if args.theme == 'dark' else
                     'background = "#faf7f0"\nforeground = "#292d32"\naccent = "#28654a"\n')
    refresh = root / '.local/bin/omarchy-usage-dashboard-refresh'
    refresh.parent.mkdir(parents=True)
    refresh.write_text('#!/bin/sh\nexit 0\n')
    refresh.chmod(0o755)
    env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=temp + '/config',
               XDG_STATE_HOME=temp + '/state', XDG_DATA_HOME=temp + '/data',
               AI_USAGE_ROOT=str(repo), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
    proc = subprocess.Popen(['quickshell', '-p', str(root), '--no-color'], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        rows = None
        for _ in range(40):
            if proc.poll() is not None:
                break
            call = subprocess.run(['quickshell', 'ipc', '-p', str(root), '--any-display',
                                   'call', 'panelqa', 'inspect'], env=env,
                                  capture_output=True, text=True)
            if call.returncode == 0:
                try:
                    rows = json.loads(call.stdout.strip())
                    if len(rows) == 3:
                        break
                except ValueError:
                    pass
            time.sleep(0.1)
        assert rows and [row.get('fresh') for row in rows] == [200, 175, 0], rows
        assert [row['total'] for row in rows] == [220, 200000175, 0], rows
        assert [row['cached'] for row in rows] == [20, 200000000, 0], rows
        assert all(row['fresh'] + row['cached'] == row['total'] for row in rows), rows
        assert 'Total including cache' in rows[1]['details'] and 'Cache reused' in rows[1]['details'], rows
        assert 'Total including cache 200,000,175' in rows[1]['details'], rows[1]
        def ipc(method, *arguments):
            call = subprocess.run(['quickshell', 'ipc', '-p', str(root), '--any-display',
                                   'call', 'panelqa', method, *arguments], env=env,
                                  capture_output=True, text=True, check=True)
            return call.stdout.strip()
        rendered = json.loads(ipc('renderedModels'))
        assert [row['share'] for row in rendered] == [1, .875, 0], rendered
        assert '175 new · 200.0M cache' in rendered[1]['text'], rendered
        print('Rendered cache-split models:', rendered)
        hours = json.loads(ipc('hours'))
        assert hours['available'] and hours['fresh'] == 375 and hours['cached'] == 200000020, hours
        assert hours['rows'][0]['tokens'] == 375 and hours['rows'][0]['cachedTokens'] == 200000020, hours
        assert hours['rows'][0]['totalTokens'] == hours['fresh'] + hours['cached'], hours
        assert any('Cache reused' in label for label in hours['labels']), hours
        print('Rendered cache-split hours:', hours)
        labels = json.loads(ipc('percentLabels'))
        assert labels and all(label.endswith('% used') for label in labels), labels
        print('Rendered percentage labels:', labels)
        watched = json.loads(ipc('watchLimits'))
        assert [row['percent'] for row in watched] == [0.98, 0.97, 0.59], watched
        assert [row['label'] for row in watched] == ['Model weekly', 'Weekly (7-day)', 'Monthly'], watched
        source = json.loads(ipc('source'))
        assert source == {'label': 'SOURCE', 'value': 'all', 'text': 'All sources'}, source
        header = json.loads(ipc('header'))
        assert header['pickerY'] == 0 and abs(header['buttonY'] - header['pickerY']) <= 3, header
        assert header['pickerX'] >= 3 and header['pickerWidth'] >= 120, header
        assert header['buttonX'] > header['pickerX'] + header['pickerWidth'], header
        assert header['buttonX'] + header['buttonWidth'] < header['columnWidth'], header
        assert header['pinnedY'] > header['pickerY'], header
        if args.capture_source:
            image_path = args.capture_source.resolve()
            image_path.unlink(missing_ok=True)
            assert ipc('captureSource', str(image_path)) == 'true'
            for _ in range(30):
                if image_path.exists(): break
                time.sleep(0.1)
            assert image_path.exists(), image_path
            print('Captured source picker:', image_path)
        if args.capture_header:
            image_path = args.capture_header.resolve()
            image_path.unlink(missing_ok=True)
            assert ipc('captureHeader', str(image_path)) == 'true'
            for _ in range(30):
                if image_path.exists(): break
                time.sleep(0.1)
            assert image_path.exists(), image_path
            print('Captured panel header:', image_path)
        before_scroll = json.loads(ipc('scrollState'))
        if args.capture_viewport:
            image_path = args.capture_viewport.resolve()
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.unlink(missing_ok=True)
            assert ipc('captureViewport', str(image_path)) == 'true'
            for _ in range(30):
                if image_path.exists(): break
                time.sleep(.1)
            assert image_path.exists(), image_path
            print('Captured constrained panel viewport:', image_path)
        if args.capture_content:
            image_path = args.capture_content.resolve()
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.unlink(missing_ok=True)
            assert ipc('captureContent', str(image_path)) == 'true'
            for _ in range(30):
                if image_path.exists(): break
                time.sleep(.1)
            assert image_path.exists(), image_path
            print('Captured complete panel content:', image_path)
        after_scroll = json.loads(ipc('scrollDown'))
        assert before_scroll['contentHeight'] > before_scroll['height'], before_scroll
        assert before_scroll['visible'] and before_scroll['outsideClip'] and before_scroll['width'] >= 12, before_scroll
        assert after_scroll['contentY'] > before_scroll['contentY'], (before_scroll, after_scroll)
        dragged = json.loads(ipc('dragScroll'))
        assert dragged['contentY'] > 0, dragged
        ipc('selectCodex')
        focused = json.loads(ipc('source'))
        assert focused == {'label': 'SOURCE', 'value': 'codex', 'text': 'ChatGPT Main'}, focused
        focused_labels = json.loads(ipc('percentLabels'))
        focused_models = json.loads(ipc('inspect'))
        assert [row['fresh'] for row in focused_models] == [175, 0], focused_models
        focused_hours = json.loads(ipc('hours'))
        assert focused_hours['rows'][0]['tokens'] == 175 and focused_hours['cached'] == 200000000, focused_hours
        if args.capture_content:
            focused_image = args.capture_content.resolve().with_name(args.capture_content.stem + '-codex.png')
            assert ipc('captureContent', str(focused_image)) == 'true'
            time.sleep(.3)
            assert focused_image.exists(), focused_image
            print('Captured complete focused panel content:', focused_image)
        hourly['schemaVersion'] = 1
        for record in hourly['providers'].values():
            record['cacheRead'] = record.pop('cachedTokens')
            record.pop('freshTokens')
        for hour in hourly['hours']:
            hour['cacheReadProviders'] = hour.pop('cachedProviders')
            hour.pop('freshProviders')
        replacement = hourly_file.with_suffix('.next'); replacement.write_text(json.dumps(hourly)); os.replace(replacement, hourly_file)
        time.sleep(.3)
        derivable = json.loads(ipc('hours'))
        assert derivable['available'] and derivable['fresh'] == 175 and derivable['cached'] == 200000000, derivable
        assert derivable['rows'] == focused_hours['rows'], derivable
        print('Legacy hourly cacheRead fallback passed')
        for record in hourly['providers'].values():
            record.pop('cacheRead')
        for hour in hourly['hours']:
            hour.pop('cacheReadProviders')
        replacement = hourly_file.with_suffix('.next'); replacement.write_text(json.dumps(hourly)); os.replace(replacement, hourly_file)
        time.sleep(.3)
        legacy = json.loads(ipc('hours'))
        assert not legacy['available'] and legacy['rows'] == [], legacy
        assert any('Waiting for updated cache split' in label for label in legacy['labels']), legacy
        print('Legacy inclusive-only hours safely withheld:', legacy)
        assert focused_labels and all(label.endswith('% used') for label in focused_labels), focused_labels
        usage_file = usage / 'codex.json'
        record = json.loads(usage_file.read_text())
        for remaining, funded, expected, alarming in [(100, 100, 0, False), (74, 100, .26, False), (10, 100, .9, True), (0, 100, 1, True), (120, 100, 0, False), (74, 0, -1, False)]:
            record['balance'] = {'remaining': remaining, 'funded': funded, 'currency': 'USD'}
            replacement = usage_file.with_suffix('.next')
            replacement.write_text(json.dumps(record))
            os.replace(replacement, usage_file)
            wallet = {}
            for _ in range(40):
                wallet = json.loads(ipc('wallet'))
                if wallet['balance'] == '$' + format(remaining, '.2f'):
                    break
                time.sleep(.1)
            time.sleep(.25)  # Let the real 160 ms meter animation settle.
            wallet = json.loads(ipc('wallet'))
            assert abs(wallet['fillRatio'] - max(0, expected)) < 1e-9, wallet
            assert wallet['meterVisible'] == (funded > 0), wallet
            assert (wallet['color'] == wallet['urgent']) == alarming, wallet
            assert abs(wallet['ratio'] - expected) < 1e-9, wallet
            assert abs(wallet['meterValue'] - expected) < 1e-9, wallet
            assert wallet['alarming'] == alarming, wallet
            expected_detail = str(round(max(0, expected) * 100)) + '% used' if funded > 0 else ''
            assert (expected_detail in wallet['detail']) if funded > 0 else wallet['detail'] == '', wallet
            print('Rendered panel wallet:', wallet)
        print('Offscreen panel cache-split model/hour rows, legacy fallback, source picker, attached scrollbar, and USED wallet meter passed')
    finally:
        proc.terminate()
        try:
            log = proc.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired:
            proc.kill()
            log = proc.communicate()[0]
        if any(error in log for error in ('ReferenceError', 'TypeError', 'Unable to assign', 'Failed to load')):
            raise RuntimeError(log)
