# -*- coding: utf-8 -*-
from django.core.exceptions import ImproperlyConfigured
from BeautifulSoup import BeautifulSoup
from oauth_tokens.base import BaseAccessToken, AccountLocked
from xml.sax import saxutils as su
import urllib
import cgi
import logging
import requests
import re

log = logging.getLogger('oauth_tokens')

class FacebookAccessToken(BaseAccessToken):

    provider = 'facebook'
    authenticate_url = 'https://www.facebook.com/dialog/oauth'
    access_token_url = 'https://graph.facebook.com/oauth/access_token'
    redirect_uri = 'http://www.facebook.com/page_not_found'
    response_decoder = lambda self,x: dict(cgi.parse_qsl(x))
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/34.0.1847.116 Chrome/34.0.1847.116 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Charset': 'windows-1251,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'gzip,deflate,sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive',
        'Host': 'www.facebook.com',
    }

    def parse_auth_form(self, page_content):
        '''
        Parse page with auth form and return tuple with (method, form action, form submit parameters)
        '''
        content = BeautifulSoup(page_content)

        form = content.find('form')
        if not form:
            raise Exception('There is no any form in response')

        method, action, data = self.get_form_attributes(form)

        data['email'] = self.username
        data['pass'] = self.password

        return (method, action, data)

    def get_form_attributes(self, form):
        data = {}
        for input in form.findAll('input'):
            if input.get('name'):
                data[input.get('name')] = input.get('value')

        action = form.get('action')
        if action[0] == '/':
            action = 'https://facebook.com' + action

        return (form.get('method').lower(), action, data)

    def parse_permissions_form(self, page_content):
        '''
        Parse page with permissions form and return tuple with (method, form action, form submit parameters)
        '''
        if 'Your Account Is Temporarily Locked' in page_content or 'Ваш аккаунт временно заблокирован' in page_content:
            raise AccountLocked("Facebook errored 'Your account is temporarily locked.'. Try to login via web browser")

        if 'Redirecting...' in page_content:
            matches =  re.findall(r'<meta http-equiv="refresh" content="0;url=(.+)" /></head>', page_content)
            url = su.unescape(urllib.unquote(matches[0]))
            return ('get', url, {})

        if '{"__html":"\u003Cform' in page_content:
            matches =  re.findall(r'{"__html":"(\\u003Cform.+/form>)"},', page_content)
            content = BeautifulSoup(matches[0].decode("unicode-escape").replace('\/', '/'))
            form = content.find('form')
        else:
            content = BeautifulSoup(page_content)
            form = content.find('form', {'id': 'uiserver_form'})

        if not form:
            raise Exception('There is no any form in response')

        data = {}
        for input in form.findAll('input'):
            if input.get('name'):
                data[input.get('name')] = input.get('value')

        if 'cancel_clicked' in data:
            del data['cancel_clicked']

        action = form.get('action')
        if action[0] == '/':
            action = 'https://facebook.com' + action

        return (form.get('method').lower(), action, data)

    def authorize(self):
        '''
        Handling specific errors
        '''
        response = super(FacebookAccessToken, self).authorize()

        if 'You are trying too often' in response.content:
            # TODO: fix it
            log.error("Vkontakte authorization request returns error 'You are trying too often'")
            raise Exception("Vkontakte authorization request returns error 'You are trying too often'")
        if 'Cookies Required' in response.content:
            response = requests.get('http://facebook.com')
            self.cookies = response.cookies
            self.authorize()
        if 'API Error Code: 191' in response.content:
            raise ImproperlyConfigured("You must specify URL '%s' in your facebook application settings" % self.redirect_uri)

        if 'Your account is temporarily locked.' in response.content:
            raise AccountLocked("Facebook errored 'Your account is temporarily locked.'. Try to login via web browser")

        return response