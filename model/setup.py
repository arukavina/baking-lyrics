import versioneer
from distutils.core import setup

desc = "Baking-Lyrics model n-gram generator factory"

setup(name='bl-model',
      author='bl-team',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      author_email='rukavina.andrei@gmail.com',
      url='https://github.com/arukavina/baking-lyrics',
      long_description=desc)
