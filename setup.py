#!/usr/bin/env python

from setuptools import setup, find_packages
)
setup(name='appengine_mailer',
      version='0.1',
      description='AppEngine Email Proxy',
      author='Mat Clayton',
      author_email='mat@mixcloud.com',
      url='https://github.com/mixcloud/appengine-mailer',
      packages=find_packages(),
      include_package_data=True,
      license="MIT license, see LICENSE file",
      long_description=open('README').read(),
)
