import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support

Plasma5Support.DataSource {
    id: exe
    engine: "executable"
    property var _cb: null
    property var _queue: []
    property bool _busy: false
    onNewData: function (sourceName, data) {
        // stdout arrives in chunks; only parse when the process has exited.
        if (data["exit code"] === undefined)
            return
        const stdout = data["stdout"] || ""
        const cb = _cb
        _cb = null
        disconnectSource(sourceName)
        _busy = false
        if (cb) {
            try { cb(JSON.parse(stdout)) } catch (e) { cb({error: stdout}) }
        }
        exe._kick()
    }
    function rpc(args, cb) {
        _queue.push({ args: args, cb: cb || null })
        _kick()
    }
    function _kick() {
        if (_busy || !_queue.length)
            return
        const job = _queue.shift()
        _cb = job.cb
        _busy = true
        connectSource("kde-ai --json " + job.args)
    }
}
