#!/usr/bin/env python

from distutils.core import setup, Distribution, Command
import os.path as path
import os

try:
    import py2exe
    build_exe = py2exe.build_exe.py2exe
    Distribution = py2exe.Distribution
    
except ImportError:
    py2exe = None
    build_exe = Command

from virtaal.__version__ import ver as virtaal_version

##############################################################################
# Windows building functions and classes

class InnoScript:
    """class that builds an InnoSetup script"""
    
    def __init__(self, name, lib_dir, dist_dir, exe_files = [], other_files = [], install_scripts = [], version = "1.0"):
        self.lib_dir = lib_dir
        self.dist_dir = dist_dir
        if not self.dist_dir.endswith(os.sep):
            self.dist_dir += os.sep
            
        self.name = name
        self.version = version
        self.exe_files = [self.chop(p) for p in exe_files]
        self.other_files = [self.chop(p) for p in other_files]
        self.install_scripts = install_scripts


    def getcompilecommand(self):
        try:
            import _winreg
            compile_key = _winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT, "innosetupscriptfile\\shell\\compile\\command")
            compilecommand = _winreg.QueryValue(compile_key, "")
            compile_key.Close()
            
        except:
            compilecommand = "compil32.exe"
        return compilecommand


    def chop(self, pathname):
        """returns the path relative to self.dist_dir"""
        assert pathname.startswith(self.dist_dir)
        return pathname[len(self.dist_dir):]


    def create(self, pathname=None):
        """creates the InnoSetup script"""
        if pathname is None:
            self.pathname = path.join(self.dist_dir, self.name + os.extsep + "iss")
          
        else:
            self.pathname = pathname
          
# See http://www.jrsoftware.org/isfaq.php for more InnoSetup config options.
        ofi = self.file = open(self.pathname, "w")
        print >> ofi, r'''; WARNING: This script has been created by py2exe. Changes to this script
; will be overwritten the next time py2exe is run!

[Setup]
AppName=%(name)s
AppVerName=%(name)s %(version)s
DefaultDirName={pf}\%(name)s
DefaultGroupName=%(name)s
OutputBaseFilename=%(name)s-%(version)s-setup
ChangesEnvironment=yes
SetupIconFile=icons\virtaal.ico

[Files]''' % {'name': self.name, 'version': self.version}
        for fpath in self.exe_files + self.other_files:
            print >> ofi, r'Source: "%s"; DestDir: "{app}\%s"; Flags: ignoreversion' % (fpath, os.path.dirname(fpath))
        print >> ofi, r'''
[Icons]
Name: "{group}\VirTaal Translation Editor"; Filename: "{app}\run_virtaal.exe";
Name: "{group}\Uninstall %(name)s"; Filename: "{uninstallexe}"''' % {'name': self.name}

        if self.install_scripts:
            print >> ofi, r"[Run]"
            
            for fpath in self.install_scripts:
                print >> ofi, r'Filename: "{app}\%s"; WorkingDir: "{app}"; Parameters: "-install"' % fpath
                
            print >> ofi
            print >> ofi, r"[UninstallRun]"
            
            for fpath in self.install_scripts:
                print >> ofi, r'Filename: "{app}\%s"; WorkingDir: "{app}"; Parameters: "-remove"' % fpath
                
        print >> ofi
        ofi.close()


    def compile(self):
        """compiles the script using InnoSetup"""
        shellcompilecommand = self.getcompilecommand()
        compilecommand = shellcompilecommand.replace('"%1"', self.pathname)
        result = os.system(compilecommand)
        if result:
            print "Error compiling iss file"
            print "Opening iss file, use InnoSetup GUI to compile manually"
            os.startfile(self.pathname)


def map_data_file (data_file):
    """remaps a data_file (could be a directory) to a different location
    This version gets rid of Lib\\site-packages, etc"""
    
    data_parts = data_file.split(os.sep)
    
    if data_parts[:2] == ["Lib", "site-packages"]:
        data_parts = data_parts[2:]
        if data_parts:
            data_file = path.join(*data_parts)
            
        else:
            data_file = ""
            
    if data_parts[:1] == ["translate"]:
        data_parts = data_parts[1:]
        if data_parts:
            data_file = path.join(*data_parts)
            
        else:
            data_file = ""
            
    return data_file


class build_exe_map(build_exe):
    """distutils py2exe-based class that builds the exe file(s) but allows mapping data files"""

    # Override
    def reinitialize_command(self, command, reinit_subcommands=0):
        if command == "install_data":
            install_data = build_exe.reinitialize_command(self, command, reinit_subcommands)
            install_data.data_files = self.remap_data_files(install_data.data_files)
            return install_data
          
        return build_exe.reinitialize_command(self, command, reinit_subcommands)


    def remap_data_files(self, data_files):
        """maps the given data files to different locations using external map_data_file function"""
        new_data_files = []
        
        for f in data_files:
            if type(f) in (str, unicode):
                f = map_data_file(f)
                
            else:
                datadir, files = f
                datadir = map_data_file(datadir)
                if datadir is None:
                    f = None
                else:
                    f = datadir, files
                  
            if f is not None:
                new_data_files.append(f)
              
        return new_data_files


class build_installer(build_exe_map):
    """distutils class that first builds the exe file(s), then creates a Windows installer using InnoSetup"""

    description = "create an executable installer for MS Windows using InnoSetup and py2exe"
    
    user_options = getattr(build_exe, 'user_options', []) + \
        [('install-script=', None,
          "basename of installation script to be run after installation or before deinstallation")]


    def initialize_options(self):
        build_exe.initialize_options(self)
        self.install_script = None


    def run(self):
        # First, let py2exe do it's work.
        build_exe.run(self)
        # create the Installer, using the files py2exe has created.
        exe_files = self.windows_exe_files + self.console_exe_files
        
        install_scripts = self.install_script
        if isinstance(install_scripts, (str, unicode)):
            install_scripts = [install_scripts]
            
        script = InnoScript(self.distribution.metadata.name, self.lib_dir, self.dist_dir, exe_files, self.lib_files,
                            version=self.distribution.metadata.version, install_scripts=install_scripts)
        print "*** creating the inno setup script***"
        script.create()
        print "*** compiling the inno setup script***"
        script.compile()
        # Note: By default the final setup.exe will be in an Output subdirectory.


##############################################################################
# Setup functions

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Programming Language :: Python",
    "Topic :: Software Development :: Localization",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Operating System :: OS Independent",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: Unix"
]


def findGTKBin():
    GTK_NAME = "libgtk"
    # Look for GTK in the user's Path as well as in some familiar locations
    paths = os.environ['Path'].split(';') + [r'C:\GTK\bin', r'C:\Program Files\GTK\bin']

    for p in paths:
        files = [path.join(p, f) for f in os.listdir(p) if path.isfile(path.join(p, f)) and f.startswith(GTK_NAME)]
        if len(files) > 0:
            return p
        
    raise Exception("""Could not find the GTK runtime.
Please place bin directory of your GTK installation in the program path.""")


def findGTKFiles():
    def parent(dir):
        return path.abspath(path.join(path.abspath(dir), '..'))
        
    def stripLeadingPath(leadingPath, p):
        return p[len(leadingPath) + 1:]

    dataFiles = []
    gtkPath = parent(findGTKBin())
    for dir in [path.join(gtkPath, p) for p in ('etc', 'share', 'lib')]:
        for dirName, _, files in os.walk(dir):
            files = [path.abspath(path.join(dirName, f)) for f in files]
            if len(files) > 0:
                dataFiles.append((stripLeadingPath(gtkPath, dirName), files))

    return dataFiles
    

class TranslateDistribution(Distribution):
    """a modified distribution class for translate"""
    def __init__(self, attrs):
        baseattrs = {}

        if py2exe:
            attrs.setdefault('data_files', []).extend(findGTKFiles())
            
            baseattrs = {
                "options": {
                    "py2exe": {
                        "packages":   ["encodings", "virtaal"],
                        "compressed": True,
                        "excludes":   ["PyLucene", "Tkconstants", "Tkinter", "tcl", "translate.misc._csv"],
                        "dist_dir":   "virtaal-win32",
                        "includes":   ["lxml", "lxml._elementpath", "psyco", "cairo", "pango", "pangocairo", "atk", "gobject"],
                        "optimize":   2,
                    }
                },

                "windows": [
                    {
                        'script': 'run_virtaal.py',
                        'icon_resources': [(1, "icons/virtaal.ico")],
                    }
                ],
                
                'zipfile':  "virtaal.zip",
                'cmdclass':  {"py2exe": build_exe_map, "innosetup": build_installer}
            }
            
            baseattrs["options"]["innosetup"] = baseattrs["options"]["py2exe"].copy()
            baseattrs["options"]["innosetup"]["install_script"] = []

        baseattrs.update(attrs)
        Distribution.__init__(self, baseattrs)


def dosetup(name, version, packages, **kwargs):
    long_description = __doc__
    #description = __doc__.split("\n", 1)[0]    
    description = "A program to do translations."
    setup(name=name,
          version=version,
          license="GNU General Public License (GPL)",
          description=description,
          long_description=long_description,
          author="Translate.org.za",
          author_email="translate-devel@lists.sourceforge.net",
          url="http://translate.sourceforge.net/wiki/virtaal/index",
          download_url="http://sourceforge.net/project/showfiles.php?group_id=91920&package_id=270877",
          platforms=["any"],
          classifiers=classifiers,
          packages=packages,
          distclass=TranslateDistribution,
          **kwargs)


def standardsetup(name, version, custompackages=[], customdatafiles=[]):        
    dosetup(name, version,
            packages=['virtaal'],
            data_files=[('virtaal', ['virtaal/data/virtaal.glade']),
                        ('mime/packages', ['virtaal/data/virtaal-mimetype.xml']),
                        ('applications', ['virtaal/data/virtaal.desktop']),
                        ('icons', ['virtaal.png', 'virtaal.ico'])],
            scripts=['run_virtaal.py'])

    
if __name__ == "__main__":
    standardsetup("VirTaal", virtaal_version)
