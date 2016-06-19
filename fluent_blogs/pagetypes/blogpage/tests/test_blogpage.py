from datetime import datetime

import django
from django.conf import settings
from django.contrib.admin import AdminSite
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory
from django.utils import translation

from fluent_blogs.admin import EntryAdmin
from fluent_blogs.models import Entry
from fluent_blogs.pagetypes.blogpage.models import BlogPage
from fluent_pages.urlresolvers import PageTypeNotMounted

try:
    from django.test.utils import override_settings
except ImportError:
    override_settings = None


class BlogPageTests(TestCase):
    """
    Testing integration between django-fluent-pages and django-fluent-blogs
    """
    if django.VERSION < (1, 8):
        urls = 'fluent_blogs.pagetypes.blogpage.tests.urls'  # Older Django

    @classmethod
    def setUpClass(cls):
        super(BlogPageTests, cls).setUpClass()
        User = get_user_model()

        Site.objects.get_or_create(id=settings.SITE_ID, defaults=dict(domain='django.localhost', name='django at localhost'))
        cls.user = User.objects.create_superuser("fluent-blogs-admin", 'admin@example.org', 'admin')

    def setUp(self):
        super(BlogPageTests, self).setUp()

        if django.VERSION >= (1, 8):
            self.overrider = override_settings(ROOT_URLCONF=self.urls)
            self.overrider.enable()

    def tearDown(self):
        if django.VERSION > (1, 8):
            self.overrider.disable()

        super(BlogPageTests, self).tearDownClass()

    def tearDown(self):
        cache.clear()  # BlogPage URLs are stored in cache

    def test_no_blogpage(self):
        """
        When there is no blog page, the system should detect this.
        """
        date = datetime(year=2016, month=5, day=1)
        entry = Entry.objects.language('en').create(author=self.user, slug='foo', publication_date=date)
        self.assertRaises(PageTypeNotMounted, lambda: entry.default_url)
        self.assertEqual(entry.get_absolute_url_format(), '/.../2016/05/{slug}/')  # slug preview should not crash.

    def test_blogpage_fallback_url(self):
        """
        Testing how translated entries appear on a ``BlogPage`` that has no translation except for the default/fallback.
        """
        page = BlogPage.objects.language('en').create(author=self.user, status=BlogPage.PUBLISHED, slug='blogpage')
        self.assertEqual(page.default_url, '/en/blogpage/')

        date = datetime(year=2016, month=5, day=1)
        entry = Entry.objects.language('en').create(author=self.user, slug='hello-en', publication_date=date)
        self.assertEqual(entry.default_url, '/en/blogpage/2016/05/hello-en/')

        # Simulate fetched entry in new language
        with translation.override('nl'):
            entry.set_current_language('nl')
            self.assertEqual(entry.default_url, '/nl/blogpage/2016/05/hello-en/')

            # Create new language
            entry.create_translation('nl', slug='hello-nl')
            self.assertEqual(entry.default_url, '/nl/blogpage/2016/05/hello-nl/')

    def test_no_blogpage_admin(self):
        """
        When there is no page type mounted, the admin page should still be accessable.
        """
        date = datetime(year=2016, month=5, day=1)
        entry = Entry.objects.language('en-us').create(author=self.user, slug='hello-fr', publication_date=date)
        url = reverse(admin_urlname(entry._meta, 'change'), args=(entry.pk,))

        # Make an admin site, avoid dependency on URLs
        admin = AdminSite()
        admin.register(Entry, EntryAdmin)
        model_admin = admin._registry[Entry]
        request = RequestFactory().get(url)
        request.user = self.user

        response = model_admin.change_view(request, str(entry.pk))
        self.assertContains(response, 'page needs to be created first')