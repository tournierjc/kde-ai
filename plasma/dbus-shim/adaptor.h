#pragma once

#include <QObject>
#include <QLocalSocket>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QStandardPaths>
#include <QProcess>

class Adaptor : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.kdeai.Agent")
public:
    explicit Adaptor(QObject *parent = nullptr) : QObject(parent) {}

public slots:
    QString Chat(const QString &sessionId, const QString &message)
    {
        const auto res = rpc(QStringLiteral("chat.send"),
                             QJsonObject{{QStringLiteral("session_id"), sessionId},
                                         {QStringLiteral("message"), message}});
        return res.value(QStringLiteral("stream_id")).toString();
    }

    QString Status()
    {
        return QString::fromUtf8(QJsonDocument(rpc(QStringLiteral("status.get"), {})).toJson(QJsonDocument::Compact));
    }

    QString ConfigGet()
    {
        return QString::fromUtf8(QJsonDocument(rpc(QStringLiteral("config.get"), {})).toJson(QJsonDocument::Compact));
    }

    bool ConfigSet(const QString &key, const QString &jsonValue)
    {
        QJsonObject patch;
        patch.insert(key, QJsonDocument::fromJson(jsonValue.toUtf8()).object().isEmpty()
                              ? QJsonValue(jsonValue)
                              : QJsonDocument::fromJson(jsonValue.toUtf8()).object().value(key));
        // treat jsonValue as a JSON literal
        QJsonValue v = QJsonValue(jsonValue);
        const auto parsed = QJsonDocument::fromJson(jsonValue.toUtf8());
        if (!parsed.isNull()) {
            if (parsed.isObject())
                v = parsed.object();
            else if (parsed.isArray())
                v = parsed.array();
            else if (parsed.isBool() || jsonValue == "true" || jsonValue == "false")
                v = QJsonValue(jsonValue == "true");
        }
        patch = QJsonObject{{key, jsonValue == "true" ? QJsonValue(true) : jsonValue == "false" ? QJsonValue(false) : QJsonValue(jsonValue)}};
        rpc(QStringLiteral("config.set"), QJsonObject{{QStringLiteral("patch"), patch}});
        return true;
    }

    QString SkillsList()
    {
        return QString::fromUtf8(QJsonDocument(rpc(QStringLiteral("skills.list"), {})).toJson(QJsonDocument::Compact));
    }

    QString Match(const QString &query)
    {
        QString q = query;
        if (q.startsWith(QLatin1String("ai ")))
            q = q.mid(3);
        else if (q.startsWith(QLatin1String("kdeai ")))
            q = q.mid(6);
        else
            return {};
        const auto st = rpc(QStringLiteral("status.get"), {});
        QString sid = st.value(QStringLiteral("active_session_id")).toString();
        if (sid.isEmpty()) {
            sid = rpc(QStringLiteral("session.create"), QJsonObject{{QStringLiteral("title"), QStringLiteral("KRunner")}})
                      .value(QStringLiteral("session_id"))
                      .toString();
        }
        rpc(QStringLiteral("chat.send"), QJsonObject{{QStringLiteral("session_id"), sid}, {QStringLiteral("message"), q}});
        return sid;
    }

signals:
    void StatusChanged(const QString &json);
    void PrivilegeRequired(const QString &json);
    void IssueAwaiting(const QString &json);

private:
    QJsonObject rpc(const QString &method, const QJsonObject &params)
    {
        QLocalSocket sock;
        const QString path = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation)
            + QStringLiteral("/kde-ai/kde-ai.sock");
        sock.connectToServer(path);
        if (!sock.waitForConnected(1000))
            return {};
        static int id = 1;
        const auto send = [&](const QString &m, const QJsonObject &p) {
            QJsonObject req{{QStringLiteral("jsonrpc"), QStringLiteral("2.0")},
                            {QStringLiteral("id"), ++id},
                            {QStringLiteral("method"), m},
                            {QStringLiteral("params"), p}};
            sock.write(QJsonDocument(req).toJson(QJsonDocument::Compact) + '\n');
            sock.flush();
            if (!sock.waitForReadyRead(5000))
                return QJsonObject{};
            const auto doc = QJsonDocument::fromJson(sock.readAll());
            return doc.object().value(QStringLiteral("result")).toObject();
        };
        send(QStringLiteral("hello"),
             QJsonObject{{QStringLiteral("protocol_version"), 1},
                         {QStringLiteral("client"), QStringLiteral("plasmoid")},
                         {QStringLiteral("auth_frontend"), QStringLiteral("polkit")},
                         {QStringLiteral("pid"), 0},
                         {QStringLiteral("locale"), QStringLiteral("en_US")}});
        return send(method, params);
    }
};
