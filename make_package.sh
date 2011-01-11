INSTALLDIR=debian/usr/lib/python3.1/dist-packages/
mkdir -p ${INSTALLDIR}
cp epdb.py debug.py shareddict.py snapshotting.py dbg.py breakpoint.py resources.py ${INSTALLDIR}
python3 -mcompileall ${INSTALLDIR}
dpkg-deb --build debian
mv debian.deb epdb.deb
