from setuptools import setup  # pragma: no cover


def read_file(file_name):
    with open(file_name) as f:
        return f.read()


setup(  # pragma: no cover
    name='errata_server',
    version='0.1a0',
    description=read_file('README.md'),
    license=read_file('LICENSE'),
    author='Matthias Dellweg',
    author_email='dellweg@atix.de',
    url='https://orcharhino.com',
    packages=[
        'errata_server',
    ],
    install_requires=[
        'asyncio',
        'aiofiles',
        'decorator',
        'click',
        'simplejson',
        'twisted',
    ],
    entry_points='''
        [console_scripts]
        errata_server=errata_server:main
    ''',
)
