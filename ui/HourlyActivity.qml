import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var hours: []
    property var unplaced: ({total: {tokens: 0, value: 0}})
    property string metric: "tokens"
    property string fontFamily: "monospace"
    property color ink: "white"
    property color muted: "#aaaaaa"
    property color edge: "#444444"
    property color accent: "#88bb99"
    property var sourceColor: function(id) { return accent }
    property var sourceName: function(id) { return id }
    property var formatHour: function(start) { return Qt.formatDateTime(new Date(Number(start) * 1000), "HH:mm") }
    property var formatHourTitle: function(hour) { return hour.title }
    property bool expanded: false
    property int selectedHour: -1
    signal hourSelected(int start)

    readonly property var descending: hours.slice().reverse()
    readonly property var topSources: {
        var totals = {}
        for (var h of hours) for (var id in h.providers || {})
            totals[id] = (totals[id] || 0) + Number(freshTokens(h.providers[id]) || 0)
        return Object.keys(totals).sort((a, b) => totals[b] - totals[a]).slice(0, 4)
    }
    readonly property var shown: expanded ? descending : descending.filter(h => h.title.endsWith("to now") || Number(h.total.tokens || 0) > 0).slice(0, 10)
    readonly property real peak: {
        var value = 1
        for (var i = 0; i < hours.length; i++) value = Math.max(value, amount(hours[i].total))
        return value
    }
    implicitHeight: content.implicitHeight

    function freshTokens(bucket) {
        if (!bucket) return 0
        if (typeof bucket.freshTokens === "number") return bucket.freshTokens
        var cached = cachedTokens(bucket)
        return cached === null ? null : Math.max(0, Number(bucket.tokens || 0) - cached)
    }
    function cachedTokens(bucket) {
        if (!bucket) return 0
        return typeof bucket.cachedTokens === "number" ? bucket.cachedTokens
             : typeof bucket.cacheRead === "number" ? bucket.cacheRead : null
    }
    function count(value) { return value === null ? "—" : Number(value || 0).toLocaleString(Qt.locale("en_US"), "f", 0) }
    function amount(bucket) { return Number(bucket ? (metric === "tokens" ? freshTokens(bucket) : bucket.value) : 0) || 0 }
    function exact(bucket) {
        if (metric === "tokens" && freshTokens(bucket) === null) return "—"
        var value = amount(bucket)
        return metric === "tokens" ? Math.round(value).toLocaleString(Qt.locale("en_US"), "f", 0)
                                   : "$" + value.toLocaleString(Qt.locale("en_US"), "f", 2)
    }
    function hourLabel(hour) {
        var duplicate = hours.filter(h => h.label === hour.label).length > 1
        return duplicate ? formatHourTitle(hour).split(" to ")[0] : formatHour(hour.start)
    }
    function segments(hour) {
        var total = Number(freshTokens(hour.total) || 0)
        if (!total) return []
        var rows = topSources.map(id => ({id: id, tokens: Number(freshTokens((hour.providers || {})[id]) || 0)}))
        var rest = Object.keys(hour.providers || {}).filter(id => topSources.indexOf(id) < 0)
            .reduce((sum, id) => sum + Number(freshTokens(hour.providers[id]) || 0), 0)
        if (rest) rows.push({id: "other", tokens: rest})
        return rows
    }

    Column {
        id: content
        width: parent.width
        spacing: 4

        Text {
            visible: root.unplaced.total && root.unplaced.total.tokens > 0
            width: parent.width; bottomPadding: 5
            text: root.count(root.freshTokens(root.unplaced.total)) + " new · " + root.count(root.cachedTokens(root.unplaced.total))
                  + " reused session-summary tokens cannot be assigned to an exact hour"
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 11
            wrapMode: Text.WordWrap
        }

        Flow {
            visible: root.metric === "tokens" && root.topSources.length > 1
            width: parent.width; spacing: 14
            Repeater {
                model: root.topSources
                Row {
                    required property string modelData
                    spacing: 6
                    Rectangle { width: 7; height: 7; radius: 4; color: root.sourceColor(parent.modelData); anchors.verticalCenter: parent.verticalCenter }
                    Text { text: root.sourceName(parent.modelData); color: root.muted; font.family: root.fontFamily; font.pixelSize: 11 }
                }
            }
            Row {
                visible: root.hours.some(h => Object.keys(h.providers || {}).some(id => root.topSources.indexOf(id) < 0))
                spacing: 6
                Rectangle { width: 7; height: 7; radius: 4; color: root.muted; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Other"; color: root.muted; font.family: root.fontFamily; font.pixelSize: 11 }
            }
        }

        Text {
            visible: root.metric === "tokens" && root.hours.some(h => root.freshTokens(h.total) === null)
            text: "Waiting for updated cache split"
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 12
            width: parent.width; wrapMode: Text.WordWrap
        }

        Text {
            visible: !root.expanded && root.descending.length > root.shown.length
            text: "Hours with activity, plus the current hour when applicable · local time"
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 11
            bottomPadding: 4
        }

        Text {
            visible: root.shown.length === 0
            text: "No event-timed usage in these hours"
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 12
            topPadding: 8; bottomPadding: 8
        }

        Repeater {
            model: root.shown
            Button {
                id: hourRow
                required property var modelData
                width: content.width
                implicitHeight: 38
                Accessible.name: root.hourLabel(modelData) + ", " + root.exact(modelData.total)
                    + (root.metric === "tokens" ? " new tokens, " + root.count(root.cachedTokens(modelData.total)) + " cache reused" : " API value")
                    + (modelData.title.endsWith("to now") ? ", current hour" : "")
                onClicked: root.hourSelected(Number(modelData.start))
                ToolTip.visible: hovered
                ToolTip.text: "New tokens " + root.count(root.freshTokens(modelData.total))
                    + " · Cache reused " + root.count(root.cachedTokens(modelData.total))
                    + " · Total including cache " + root.count(modelData.total.tokens)
                background: Rectangle {
                    radius: 3
                    color: hourRow.down || Number(hourRow.modelData.start) === root.selectedHour
                        ? Qt.alpha(root.accent, 0.16) : hourRow.hovered ? Qt.alpha(root.ink, 0.055) : "transparent"
                    border.color: hourRow.activeFocus ? root.accent : "transparent"
                }
                contentItem: RowLayout {
                    spacing: 14
                    Text {
                        text: root.hourLabel(hourRow.modelData)
                        color: hourRow.modelData.title.endsWith("to now") ? root.ink : root.muted
                        font.family: root.fontFamily; font.pixelSize: 12
                        Layout.preferredWidth: 92
                    }
                    Item {
                        Layout.fillWidth: true; implicitHeight: 9
                        Rectangle { anchors.fill: parent; radius: 4; color: root.edge }
                        Row {
                            height: parent.height
                            width: parent.width * Math.min(1, root.amount(hourRow.modelData.total) / root.peak)
                            spacing: 0
                            Repeater {
                                model: root.metric === "tokens" ? root.segments(hourRow.modelData) : (root.amount(hourRow.modelData.total) ? [{id:"value",tokens:1}] : [])
                                Rectangle {
                                    required property var modelData
                                    height: 9
                                    width: root.metric === "tokens"
                                        ? parent.width * modelData.tokens / Math.max(1, root.amount(hourRow.modelData.total))
                                        : parent.width
                                    color: modelData.id === "other" ? root.muted
                                           : modelData.id === "value" ? root.accent : root.sourceColor(modelData.id)
                                }
                            }
                        }
                    }
                    Text {
                        text: root.exact(hourRow.modelData.total) + (root.metric === "tokens" ? " new" : "")
                        color: root.ink; font.family: root.fontFamily; font.pixelSize: 12
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 118
                    }
                    Text {
                        visible: root.metric === "tokens"
                        text: root.count(root.cachedTokens(hourRow.modelData.total)) + " cache"
                        color: root.muted; font.family: root.fontFamily; font.pixelSize: 11
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 160
                    }
                }
            }
        }

        Button {
            visible: root.descending.length > 10
            text: root.expanded ? "Show recent hours" : "Show all " + root.descending.length + " elapsed hours"
            Accessible.name: text
            onClicked: root.expanded = !root.expanded
            font.family: root.fontFamily; font.pixelSize: 12
            implicitHeight: 32
            background: Rectangle { radius: 3; color: parent.hovered ? Qt.alpha(root.ink, 0.08) : "transparent" }
            contentItem: Text { text: parent.text; color: root.accent; font: parent.font; verticalAlignment: Text.AlignVCenter }
        }

    }
}
