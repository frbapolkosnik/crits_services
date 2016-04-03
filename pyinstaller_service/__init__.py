from builtins import str
import logging
import zlib

from django.core.urlresolvers import reverse
from hashlib import md5, sha1, sha256
from PyInstaller.utils.cliutils.archive_viewer import get_archive

from crits.raw_data.handlers import handle_raw_data_file
from crits.services.core import Service
from crits.vocabulary.relationships import RelationshipTypes

logger = logging.getLogger(__name__)


class pyinstallerService(Service):
    """
    Get information about a binary using pyinstaller.

    """

    name = "pyinstaller"
    version = '0.0.1'
    template = "pyinstaller_service_template.html"
    description = "Extract information from a binary generated by pyinstaller."
    supported_types = ['Sample']

    @staticmethod
    def valid_for(obj):
        """
        Check to see if this was built with pyinstaller.
        """

        if not obj.filedata:
            return False

        #hexstring = "cffaedfe07000001030000800200"
        return True

    def get_data(self, nm, arch):
        if type(arch.toc) is type({}):
            (ispkg, pos, lngth) = arch.toc.get(nm, (0, None, 0))
            if pos is None:
                return None
            arch.lib.seek(arch.start + pos)
            return zlib.decompress(arch.lib.read(lngth))
        ndx = arch.toc.find(nm)
        dpos, dlen, ulen, flag, typcd, nm = arch.toc[ndx]
        x, data = arch.extract(ndx)
        return data

    def run_archive_viewer(self, obj):
        """
        Get data using the archive viewer.
        """

        safe = [
            'pyi_carchive',
            'pyi_rth_win32comgenpy',
            '_pyi_bootstrap',
            '_pyi_egg_install.py'
        ]

        # This doesn't work. Everything is showing as an invalid CArchive file.
        with self._write_to_file() as tmp_file:
            try:
                arch = get_archive(tmp_file)
                if type(arch.toc) == type({}):
                    toc = arch.toc
                else:
                    toc = arch.toc.data
                for t in toc:
                    d = {'Position': t[0],
                         'Length': t[1],
                         'Uncompressed': t[2],
                         'IsCompressed': t[3],
                         'Type': t[4],
                         'RawData': ""
                    }
                    if t[4] == 's' and t[5] not in safe:
                        try:
                            block = self.get_data(t[5], arch).encode('utf-8',
                                                                     "ignore")
                        except:
                            self._info("%s: Block not valid utf-8. Trying utf-16." % t[5])
                        try:
                            block = self.get_data(t[5], arch).encode('utf-16',
                                                                     "ignore")
                        except:
                            self._info("%s: Block not valid utf-16. Trying utf-32." % t[5])
                        try:
                            block = self.get_data(t[5], arch).encode('utf-32',
                                                                     "ignore")
                        except:
                            self._info("%s: Block not valid utf-32. Trying latin-1." % t[5])
                        try:
                            block = self.get_data(t[5], arch).encode('latin-1',
                                                                     'ignore')
                        except:
                            self._info("%s: Block not valid latin-1. Done trying." % t[5])
                            block = None
                        if block is not None:
                            bmd5 = md5(block).hexdigest()
                            bsha1 = sha1(block).hexdigest()
                            bsha256 = sha256(block).hexdigest()
                            block = block.replace('http', 'hxxp')
                            description = '"%s" pulled from Sample\n\n' % t[5]
                            description += 'MD5: %s\n' % bmd5
                            description += 'SHA1: %s\n' % bsha1
                            description += 'SHA256: %s\n' % bsha256
                            title = t[5]
                            data_type = "Python"
                            tool_name = "pyinstaller_service"
                            result = handle_raw_data_file(
                                block,
                                obj.source,
                                user=self.current_task.username,
                                description=description,
                                title=title,
                                data_type=data_type,
                                tool_name=tool_name,
                            )
                            if result['success']:
                                self._info("RawData added for %s" % t[5])
                                res = obj.add_relationship(
                                    rel_item=result['object'],
                                    rel_type=RelationshipTypes.CONTAINED_WITHIN,
                                    rel_confidence="high",
                                    analyst=self.current_task.username
                                )
                                if res['success']:
                                    obj.save(username=self.current_task.username)
                                    result['object'].save(username=self.current_task.username)
                                    url = reverse('crits.core.views.details',
                                                args=('RawData',
                                                        result['_id']))
                                    url = '<a href="%s">View Raw Data</a>' % url
                                    d['RawData'] = url
                                    self._info("Relationship added for %s" % t[5])
                                else:
                                    self._info("Error adding relationship: %s" % res['message'])
                            else:
                                self._info(
                                    "RawData addition failed for %s:%s" % (t[5],
                                                                        result['message'])
                                )
                    self._add_result("Info", t[5], d)
            except Exception as e:
                self._info("Error: %s" % str(e))

    def run(self, obj, config):
        """
        Run pyinstaller service
        """

        self.run_archive_viewer(obj)
        self.current_task.finish()
