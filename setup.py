from setuptools import setup
from restub import __version__
setup(
    name='restub',
    version=__version__,
    description='RESTub - REST Service Mocking',
    license='MIT',
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: MIT License',
    ],
    author='Igor Tolkachnikov',
    author_email='i.tolkachnikov@gmail.com',
    url='https://github.com/everhide/restub',
    packages=['restub'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    tests_require=['requests', 'urllib3']
)
