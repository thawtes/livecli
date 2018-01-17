from __future__ import print_function
import re

from livecli.plugin import Plugin
from livecli.plugin.api import http
from livecli.plugin.api import useragents
from livecli.plugin.api import validate
from livecli.stream import HLSStream


class Kanal7(Plugin):
    url_re = re.compile(r"https?://(?:www.)?kanal7.com/canli-izle")
    iframe_re = re.compile(r'iframe .*?src="(http://[^"]*?)"')
    stream_re = re.compile(r'''tp_file\s+=\s+['"](http[^"]*?)['"]''')

    @classmethod
    def can_handle_url(cls, url):
        return cls.url_re.match(url) is not None

    def find_iframe(self, url):
        res = http.get(url)
        # find iframe url
        iframe = self.iframe_re.search(res.text)
        iframe_url = iframe and iframe.group(1)
        if iframe_url:
            self.logger.debug("Found iframe: {}", iframe_url)
        return iframe_url

    def _get_streams(self):
        iframe1 = self.find_iframe(self.url)
        if iframe1:
            iframe2 = self.find_iframe(iframe1)
            if iframe2:
                ires = http.get(iframe2)
                stream_m = self.stream_re.search(ires.text)
                stream_url = stream_m and stream_m.group(1)
                if stream_url:
                    yield "live", HLSStream(self.session, stream_url, headers={"Referer": iframe2})
            else:
                self.logger.error("Could not find second iframe, has the page layout changed?")
        else:
            self.logger.error("Could not find iframe, has the page layout changed?")


__plugin__ = Kanal7
