#!/usr/bin/env python
import re

from livecli.plugin import Plugin, PluginOptions
from livecli.plugin.api import http, validate
from livecli.plugin.api import useragents
from livecli.stream import HLSStream


class TVPlayer(Plugin):
    context_url = "http://tvplayer.com/watch/context"
    api_url = "http://api.tvplayer.com/api/v2/stream/live"
    login_url = "https://tvplayer.com/account/login"
    update_url = "https://tvplayer.com/account/update-detail"
    dummy_postcode = "SE1 9LT"  # location of ITV HQ in London

    url_re = re.compile(r"https?://(?:www.)?tvplayer.com/(:?watch/?|watch/(.+)?)")
    stream_attrs_re = re.compile(r'data-(resource|token|channel-id)\s*=\s*"(.*?)"', re.S)
    data_id_re = re.compile(r'data-id\s*=\s*"(.*?)"', re.S)
    login_token_re = re.compile(r'input.*?name="token".*?value="(\w+)"')
    stream_schema = validate.Schema({
        "tvplayer": validate.Schema({
            "status": u'200 OK',
            "response": validate.Schema({
                "stream": validate.url(scheme=validate.any("http", "https")),
                validate.optional("drmToken"): validate.any(None, validate.text)
            })
        })
    },
        validate.get("tvplayer"),
        validate.get("response"))
    context_schema = validate.Schema({
        "validate": validate.text,
        validate.optional("token"): validate.text,
        "platform": {
            "key": validate.text
        }
    })
    options = PluginOptions({
        "email": None,
        "password": None
    })

    @classmethod
    def can_handle_url(cls, url):
        match = TVPlayer.url_re.match(url)
        return match is not None

    def __init__(self, url):
        super(TVPlayer, self).__init__(url)
        http.headers.update({"User-Agent": useragents.CHROME})

    def authenticate(self, username, password):
        res = http.get(self.login_url)
        match = self.login_token_re.search(res.text)
        token = match and match.group(1)
        res2 = http.post(self.login_url, data=dict(email=username, password=password, token=token),
                         allow_redirects=False)
        # there is a 302 redirect on a successful login
        return res2.status_code == 302

    def _get_stream_data(self, resource, channel_id, token, service=1):
        # Get the context info (validation token and platform)
        self.logger.debug("Getting stream information for resource={0}".format(resource))
        context_res = http.get(self.context_url, params={"resource": resource,
                                                         "gen": token})
        context_data = http.json(context_res, schema=self.context_schema)
        self.logger.debug("Context data: {0}", str(context_data))

        # get the stream urls
        res = http.post(self.api_url, data=dict(
            service=service,
            id=channel_id,
            validate=context_data["validate"],
            token=context_data.get("token"),
            platform=context_data["platform"]["key"]),
            raise_for_status=False)

        return http.json(res, schema=self.stream_schema)

    def _get_stream_attrs(self, page):
        stream_attrs = dict((k.replace("-", "_"), v.strip('"')) for k, v in self.stream_attrs_re.findall(page.text))

        if not stream_attrs.get("channel_id"):
            m = self.data_id_re.search(page.text)
            stream_attrs["channel_id"] = m and m.group(1)

        self.logger.debug("Got stream attributes: {0}", str(stream_attrs))
        valid = True
        for a in ("channel_id", "resource", "token"):
            if a not in stream_attrs:
                self.logger.debug("Missing '{0}' from stream attributes", a)
                valid = False

        return stream_attrs if valid else {}

    def _get_streams(self):
        if self.get_option("email") and self.get_option("password"):
            if not self.authenticate(self.get_option("email"), self.get_option("password")):
                self.logger.warning("Failed to login as {0}".format(self.get_option("email")))

        # find the list of channels from the html in the page
        self.url = self.url.replace("https", "http")  # https redirects to http
        res = http.get(self.url)

        if "enter your postcode" in res.text:
            self.logger.info("Setting your postcode to: {0}. "
                             "This can be changed in the settings on tvplayer.com", self.dummy_postcode)
            res = http.post(self.update_url,
                            data=dict(postcode=self.dummy_postcode),
                            params=dict(return_url=self.url))

        stream_attrs = self._get_stream_attrs(res)
        if stream_attrs:
            stream_data = self._get_stream_data(**stream_attrs)

            if stream_data:
                if stream_data.get("drmToken"):
                    self.logger.error("This stream is protected by DRM can cannot be played")
                    return
                else:
                    return HLSStream.parse_variant_playlist(self.session, stream_data["stream"])
        else:
            if "need to login" in res.text:
                self.logger.error(
                    "You need to login using --tvplayer-email/--tvplayer-password to view this stream")


__plugin__ = TVPlayer
