INSTALLDIR=debian/usr/lib/python3.1/dist-packages/
BINDIR=debian/usr/bin
DBGMODSDIR=debian/usr/share/epdb/dbgmods
mkdir -p ${INSTALLDIR}
cp epdb.py debug.py shareddict.py snapshotting.py dbg.py breakpoint.py resources.py asyncmd.py ${INSTALLDIR}
python3 -mcompileall ${INSTALLDIR}
mkdir -p ${DBGMODSDIR}
cp dbgmods/* ${DBGMODSDIR}
mkdir -p ${BINDIR}
cp epdb.py ${BINDIR}/epdb
chmod 755 ${BINDIR}/epdb
dpkg-deb --build debian
mv debian.deb epdb.deb
