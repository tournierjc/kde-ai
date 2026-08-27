import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support

Plasma5Support.DataSource {
    id: exe
    engine: "executable"
    property var _cb: null
    onNewData: function (sourceName, data) {
        const stdout = data["stdout"] || ""
        if (_cb) {
            try { _cb(JSON.parse(stdout)) } catch (e) { _cb({error: stdout}) }
        }
        disconnectSource(sourceName)
    }
    function rpc(args, cb) {
        _cb = cb
        connectSource("kde-ai --json " + args)
    }
}
