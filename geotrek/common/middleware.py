import re

from django.utils import translation
from django.utils.translation.trans_real import get_supported_language_variant


language_code_prefix_re = re.compile(r'^/api/([\w-]+)(/|$)')


def get_language_from_path(path):
    from django.conf import settings
    supported = settings.LANGUAGES
    regex_match = language_code_prefix_re.match(path)
    if not regex_match:
        return None
    lang_code = regex_match.group(1)
    try:
        return get_supported_language_variant(lang_code, supported)
    except LookupError:
        return None


class APILocaleMiddleware(object):

    def process_request(self, request):
        language = get_language_from_path(request.path_info)
        if language:
            translation.activate(language)
            request.LANGUAGE_CODE = translation.get_language()
