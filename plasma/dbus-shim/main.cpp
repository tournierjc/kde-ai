#include <QCoreApplication>
#include <QDBusConnection>
#include "adaptor.h"

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    Adaptor adaptor;
    QDBusConnection bus = QDBusConnection::sessionBus();
    bus.registerService(QStringLiteral("org.kde.kdeai"));
    bus.registerObject(QStringLiteral("/Agent"), &adaptor, QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals);
    bus.registerObject(QStringLiteral("/runner"), &adaptor, QDBusConnection::ExportAllSlots);
    return app.exec();
}
