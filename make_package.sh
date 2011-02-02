INSTALLDIR=debian/usr/lib/python3.1/dist-packages/
DBGMODSDIR=debian/usr/share/epdb/dbgmods
mkdir -p ${INSTALLDIR}
cp epdb.py debug.py shareddict.py snapshotting.py dbg.py breakpoint.py resources.py asyncmd.py ${INSTALLDIR}
python3 -mcompileall ${INSTALLDIR}
mkdir -p ${DBGMODSDIR}
cp dbgmods/* ${DBGMODSDIR}
dpkg-deb --build debian
mv debian.deb epdb.deb
