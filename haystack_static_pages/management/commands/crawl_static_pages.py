import cookielib
import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.urlresolvers import reverse, reverse_lazy
from django.utils import translation
from django.utils.html import escape
from optparse import make_option

from bs4 import BeautifulSoup

from haystack_static_pages.models import StaticPage


class Command(BaseCommand):
    # option_list deprecated since version 1.8:
    # You should now override the add_arguments() method to add custom arguments accepted by your command.
    """
    option_list = BaseCommand.option_list + (
        make_option('-p', '--port', action='store', dest='port', default=None,
            help='The port number to use for internal urls.'),
        make_option('-l', '--language', action='store', dest='language', default=None,
            help='The language to use when requesting the page'),
    )
    """
    help = 'Setup static pages defined in HAYSTACK_STATIC_PAGES for indexing by Haystack'
    cmd = 'crawl_static_pages [-p PORT] [-l LANG]'

    def handle(self, *args, **options):
        if args:
            raise CommandError('Usage is: %s' % cmd)

        self.port = options.get('port')

        if self.port:
            if not self.port.isdigit():
                raise CommandError('%r is not a valid port number.' % self.port)
            else:
                self.port = int(self.port)

        count = 0

        self.language = options.get('language')

        if self.language:
            translation.activate(self.language)

        session = requests.Session()

        # login
        login_data = {}
        if hasattr(settings, 'HAYSTACK_STATIC_LOGIN_AUTH'):
            login_url = '%s%s' % (settings.SERVER_URL, reverse(settings.HAYSTACK_STATIC_LOGIN_PAGE))
            session.get(login_url)
            login_data = settings.HAYSTACK_STATIC_LOGIN_AUTH
            login_data.update({'csrfmiddlewaretoken': session.cookies.get('csrftoken')})

            session.post(login_url, data=login_data, cookies=session.cookies)

        for url in settings.HAYSTACK_STATIC_PAGES:

            if not url.startswith('http://'):
                if self.port:
                    url = '%s:%r%s' % (settings.SERVER_URL, self.port, reverse(url))
                else:
                    url = '%s%s' % (settings.SERVER_URL, reverse(url))

            print 'Analyzing %s...' % url

            try:
                page = StaticPage.objects.get(url=url)
                print '%s already exists in the index, updating...' % url
            except StaticPage.DoesNotExist:
                print '%s is new, adding...' % url
                page = StaticPage(url=url)
                pass

            try:
                html = session.get(url, cookies=session.cookies).content
                soup = BeautifulSoup(html, "html.parser")
                page_content = soup.find(class_='content').get_text()
            except Exception as e:
                print "Error while reading '%s:%s'" % (url, e)
                continue

            try:
                page.title = escape(soup.head.title.string)
            except AttributeError:
                page.title = 'Untitled'
            meta = soup.find('meta', attrs={'name': 'description'})
            if meta:
                page.description = meta.get('content', '')
            else:
                page.description = ''
            page.language = soup.html.get('lang', 'en')
            page.content = page_content
            page.save()
            count += 1


        print 'Crawled %d static pages' % count
