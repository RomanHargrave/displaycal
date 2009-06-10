#!/usr/bin/env python

"""
manifest.py 2009-03 Florian Hoech

Provides the following functionality:
* Create, parse and write MS Windows Manifest files
* Find files which are part of an assembly, by looking for shared and 
  private assemblies
* Update manifest resources in dll/exe files

Implemented:
* Shared and private assemblies support
* Publisher configuration support (.policy files)
* application configuration support (.config files)

Not implemented:
* Manifest validation (only very basic sanity checks are currently in place)
* comClass, typelib, comInterfaceProxyStub, windowClass subelements of the 
  file element
* comInterfaceExternalProxyStub, windowClass subelements of the assembly 
  element

Reference:
About Isolated Applications and Side-by-side Assemblies
http://msdn.microsoft.com/en-us/library/aa374029(VS.85).aspx
"""
try:
    import hashlib
except ImportError, detail:
    hashlib = None
    print 'I: ... file hash calculation unavailable -', detail
import os.path
from glob import glob
from xml.dom import Node, minidom
from xml.dom.minidom import Document, Element

Document.aChild = Document.appendChild
Document.cE = Document.createElement
Document.cT = Document.createTextNode
Document.getEById = Document.getElementById
Document.getEByTN = Document.getElementsByTagName
Element.aChild = Element.appendChild
Element.getA = Element.getAttribute
Element.getEByTN = Element.getElementsByTagName
Element.remA = Element.removeAttribute
Element.setA = Element.setAttribute

try:
    import resource
except ImportError, detail:
    resource = None
    print 'I: ... manifest resource access unavailable -', detail

RT_MANIFEST = 24

def getChildElementsByTagName(self, tagName):
    """ Return child elements of type tagName if found, else [] """
    result = []
    for child in self.childNodes:
        if isinstance(child, Element):
            if child.tagName == tagName:
                result.append(child)
    return result

def getFirstChildElementByTagName(self, tagName):
    """ Return the first element of type tagName if found, else None """
    for child in self.childNodes:
        if isinstance(child, Element):
            if child.tagName == tagName:
                return child
    return None

Document.getCEByTN = getChildElementsByTagName
Document.getFCEByTN = getFirstChildElementByTagName
Element.getCEByTN = getChildElementsByTagName
Element.getFCEByTN = getFirstChildElementByTagName

class _Dummy:
    pass

class File(resource.File if resource else _Dummy):
    """ A file referenced by an assembly inside a manifest. """
    def __init__(self, filename="", hashalg=None, hash=None, comClasses=None, 
                 typelibs=None, comInterfaceProxyStubs=None, 
                 windowClasses=None):
        if resource:
            resource.File.__init__(self, filename)
        else:
            self.filename = filename
        self.name = os.path.basename(filename)
        self.hashalg = hashalg.upper() if hashalg else None
        if os.path.isfile(filename) and hashalg and hashlib:
            self.calc_hash()
        else:
            self.hash = hash
        self.comClasses = comClasses or [] # TO-DO: implement
        self.typelibs = typelibs or [] # TO-DO: implement
        self.comInterfaceProxyStubs = comInterfaceProxyStubs or [] # TO-DO: implement
        self.windowClasses = windowClasses or [] # TO-DO: implement
    def calc_hash(self, hashalg=None):
        """ Calculate the hash of the file. Will be called automatically from 
        the constructor if the file exists and hashalg is given, but may 
        also be called manually e.g. to update the hash if the file has 
        changed. """
        fd = open(self.filename, "rb")
        buf = fd.read()
        fd.close()
        if hashalg:
            self.hashalg = hashalg.upper()
        self.hash = getattr(hashlib, self.hashalg.lower())(buf).hexdigest()

class InvalidManifestError(Exception):
    pass

class Manifest():
    def __init__(self, manifestVersion=None, noInheritable=False, 
                 noInherit=False, type_=None, name=None, language=None, 
                 processorArchitecture=None, version=None, 
                 publicKeyToken=None, description=None, 
                 requestedExecutionLevel=None, uiAccess=None, 
                 dependentAssemblies=None, files=None, 
                 comInterfaceExternalProxyStubs=None):
        """ Manifest constructor.
        
        To build a basic manifest for your application:
          mf = Manifest(type='win32', name='YourAppName', language='*', 
                        processorArchitecture='x86', version=[1, 0, 0, 0])
        
        To write the XML to a manifest file:
          mf.writexml("YourAppName.exe.manifest")
        or
          mf.writeprettyxml("YourAppName.exe.manifest")
        """
        self.filename = None
        self.optional = None
        self.manifestType = "assembly"
        self.manifestVersion = manifestVersion or [1, 0]
        self.noInheritable = noInheritable
        self.noInherit = noInherit
        self.type = type_
        self.name = name
        self.language = language
        self.processorArchitecture = processorArchitecture
        self.version = version
        self.publicKeyToken = publicKeyToken
        # public key token
        # "A 16-character hexadecimal string that represents the last 8 bytes 
        # of the SHA-1 hash of the public key under which the assembly is 
        # signed. The public key used to sign the catalog must be 2048 bits 
        # or greater. Required for all shared side-by-side assemblies."
        # http://msdn.microsoft.com/en-us/library/aa375692(VS.85).aspx
        self.applyPublisherPolicy = None
        self.description = None
        self.requestedExecutionLevel = requestedExecutionLevel
        self.uiAccess = uiAccess
        self.dependentAssemblies = dependentAssemblies or []
        self.bindingRedirects = []
        self.files = files or []
        self.comInterfaceExternalProxyStubs = comInterfaceExternalProxyStubs or [] # TO-DO: implement
    
    def add_dependent_assembly(self, manifestVersion=None, noInheritable=False, 
                 noInherit=False, type_=None, name=None, language=None, 
                 processorArchitecture=None, version=None, 
                 publicKeyToken=None, description=None, 
                 requestedExecutionLevel=None, uiAccess=None, 
                 dependentAssemblies=None, files=None, 
                 comInterfaceExternalProxyStubs=None):
        """ Shortcut for:
        manifest.dependentAssemblies.append(Manifest(*args, *kwargs)) """
        self.dependentAssemblies.append(Manifest(manifestVersion, 
                                        noInheritable, noInherit, type_, name, 
                                        language, processorArchitecture, 
                                        version, publicKeyToken, description, 
                                        requestedExecutionLevel, uiAccess, 
                                        dependentAssemblies, files, 
                                        comInterfaceExternalProxyStubs))
    
    def add_file(self, name="", hashalg="", hash="", comClasses=None, 
                 typelibs=None, comInterfaceProxyStubs=None, 
                 windowClasses=None):
        """ Shortcut for:
        manifest.files.append(File(*args, *kwargs)) """
        self.files.append(File(name, hashalg, hash, comClasses, 
                          typelibs, comInterfaceProxyStubs, windowClasses))
    
    def find_files(self):
        """ Search shared and private assemblies and return a list of all 
        related files if found. If any files are not found, return an empty 
        list."""
        if None in (self.processorArchitecture, self.name, self.publicKeyToken, 
                    self.version):
                        return []
        files = []
        # search winsxs
        winsxs = os.path.join(os.getenv('SystemRoot'), 'WinSxS')
        if os.path.isdir(winsxs):
            manifests = os.path.join(winsxs, "Manifests")
            if os.path.isdir(manifests):
                for manifestpth in glob(os.path.join(manifests, 
                                                    '%s_%s_%s_%s_*.manifest' % 
                                                    (self.processorArchitecture, 
                                                     self.name, 
                                                     self.publicKeyToken, 
                                                     ".".join([str(i) for i in self.version])))):
                    assemblynm = os.path.basename(os.path.splitext(manifestpth)[0])
                    if not os.path.isfile(manifestpth):
                        print "W: No such file", manifestpth, "part of assembly", assemblynm
                        continue
                    print "I: Found manifest", manifestpth
                    assemblydir = os.path.join(winsxs, assemblynm)
                    if not os.path.isdir(assemblydir):
                        print "W: No such dir", assemblydir
                        continue
                    try:
                        manifest = ManifestFromXMLFile(manifestpth)
                    except Exception, exc:
                        print "E:", manifestpth, str(exc)
                        pass
                    else:
                        rfiles = []
                        for file_ in self.files or manifest.files:
                            fn = os.path.join(assemblydir, file_.name)
                            if os.path.isfile(fn):
                                rfiles.append(fn)
                            else:
                                print "W: No such file", fn, "part of assembly", assemblynm
                                # if any of our files does not exist,
                                # the assembly is incomplete
                                rfiles = []
                                break
                        if rfiles:
                            files.append(manifestpth)
                            files.extend(rfiles)
                            return files
                    break
            else:
                print "W: No such dir", manifests
        else:
            print "W: No such dir", winsxs
        # search for private assemblies
        if not self.filename:
            return []
        dirnm = os.path.dirname(self.filename)
        # if embedded in a dll the assembly may have the same name as the 
        # dll, so we need to make sure we don't search for *.dll.dll
        assemblynm, ext = os.path.splitext(self.name)
        if ext.lower() == ".dll":
            # discard the extension
            pass
        else:
            assemblynm = self.name
        for path in [os.path.join(dirnm, self.language or "*"),
                     os.path.join(dirnm, self.language or "*", assemblynm), 
                     dirnm, 
                     os.path.join(dirnm, assemblynm)]:
            for ext in (".dll", ".manifest"):
                # private assemblies can have the manifest either as 
                # separate file or embedded in a DLL
                manifestpth = os.path.join(path, assemblynm + ext)
                if not os.path.isfile(manifestpth):
                    print "W: No such file", manifestpth, "part of assembly", assemblynm
                    continue
                print "I: Found manifest", manifestpth
                try:
                    if ext == ".dll":
                        manifest = ManifestFromResFile(manifestpth, [1])
                    else:
                        manifest = ManifestFromXMLFile(manifestpth)
                except Exception, exc:
                    print "E:", manifestpth, str(exc)
                    pass
                else:
                    rfiles = []
                    for file_ in self.files or manifest.files:
                        fn = os.path.join(path, file_.name)
                        if os.path.isfile(fn):
                            rfiles.append(fn)
                        else:
                            print "W: No such file", fn, "part of assembly", assemblynm
                            # if any of our files does not exist,
                            # the assembly is incomplete
                            return []
                    files.append(manifestpth)
                    files.extend(rfiles)
                break
            if not os.path.isfile(manifestpth):
                for file_ in self.files:
                    fn = os.path.join(path, file_.name)
                    if os.path.exists(fn):
                        # if any of our files does exist without the manifest 
                        # in the same dir, the assembly is incomplete
                        return []
        return files
    
    def load_dom(self, domtree, initialize=True):
        """ Load manifest from DOM tree.
        If initialize is True (default), reset existing attributes first."""
        if domtree.nodeType == Node.DOCUMENT_NODE:
            rootElement = domtree.documentElement
        elif domtree.nodeType == Node.ELEMENT_NODE:
            rootElement = domtree
        else:
            raise InvalidManifestError("Invalid root element node type " + 
                                       str(rootElement.nodeType) + 
                                       " - has to be one of (DOCUMENT_NODE, ELEMENT_NODE)")
        allowed_names = ("assembly", "assemblyBinding", "configuration", 
                         "dependentAssembly")
        if rootElement.tagName not in allowed_names:
            raise InvalidManifestError("Invalid root element <" + 
                                       rootElement.tagName + 
                                       "> - has to be one of " + 
                                       repr(allowed_names))
        # print "I: loading manifest metadata from element <%s>" % \
              # rootElement.tagName
        if rootElement.tagName == "configuration":
            for windows in rootElement.getCEByTN("windows"):
                for assemblyBinding in windows.getCEByTN("assemblyBinding"):
                    self.load_dom(assemblyBinding)
        else:
            if initialize:
                self.__init__()
            self.manifestType = rootElement.tagName
            self.manifestVersion = [int(i) for i in (rootElement.getA("manifestVersion") or "1.0").split(".")]
            self.noInheritable = bool(rootElement.getFCEByTN("noInheritable"))
            self.noInherit = bool(rootElement.getFCEByTN("noInherit"))
            for assemblyIdentity in rootElement.getCEByTN("assemblyIdentity"):
                self.type = assemblyIdentity.getA("type")
                self.name = assemblyIdentity.getA("name")
                self.language = assemblyIdentity.getA("language")
                self.processorArchitecture = assemblyIdentity.getA("processorArchitecture")
                self.version = [int(i) for i in (assemblyIdentity.getA("version") or "0.0.0.0").split(".")]
                self.publicKeyToken = assemblyIdentity.getA("publicKeyToken")
            for publisherPolicy in rootElement.getCEByTN("publisherPolicy"):
                self.applyPublisherPolicy = (publisherPolicy.getA("apply") or "").lower() == "yes"
            for description in rootElement.getCEByTN("description"):
				if description.firstChild:
					self.description = description.firstChild.wholeText
            for trustInfo in rootElement.getCEByTN("trustInfo"):
                for security in trustInfo.getCEByTN("security"):
                    for requestedPrivileges in security.getCEByTN("requestedPrivileges"):
                        for requestedExecutionLevel in requestedPrivileges.getCEByTN("requestedExecutionLevel"):
                            self.requestedExecutionLevel = requestedExecutionLevel.getA("level")
                            self.uiAccess = (requestedExecutionLevel.getA("uiAccess") or "").lower() == "true"
            for dependency in (rootElement.getCEByTN("dependency") if 
                               rootElement.tagName != "assemblyBinding" else 
                               [rootElement]):
                for dependentAssembly in dependency.getCEByTN("dependentAssembly"):
                    manifest = ManifestFromDOM(dependentAssembly)
                    manifest.optional = (dependency.getA("optional") or "").lower() == "yes"
                    self.dependentAssemblies.append(manifest)
            for bindingRedirect in rootElement.getCEByTN("bindingRedirect"):
                oldVersion = [[int(i) for i in part.split(".")] for part in bindingRedirect.getA("oldVersion").split("-")]
                newVersion = [int(i) for i in bindingRedirect.getA("newVersion").split(".")]
                self.bindingRedirects.append((oldVersion, newVersion))
            for file_ in rootElement.getCEByTN("file"):
                self.add_file(name=file_.getA("name"),
                              hashalg=file_.getA("hashalg"),
                              hash=file_.getA("hash"))
    
    def parse(self, filename_or_file):
        """ Load manifest from file or file object """
        self.load_dom(minidom.parse(filename_or_file))
        if isinstance(filename_or_file, (str, unicode)):
            self.filename = filename_or_file
        else:
            self.filename = filename_or_file.filename
    
    def parse_string(self, xmlstr):
        """ Load manifest from XML string """
        self.load_dom(minidom.parseString(xmlstr))
    
    def todom(self):
        """ Return the manifest as DOM tree """
        doc = Document()
        docE = doc.cE(self.manifestType)
        if self.manifestType == "assemblyBinding":
            cfg = doc.cE("configuration")
            win = doc.cE("windows")
            win.aChild(docE)
            cfg.aChild(win)
            doc.aChild(cfg)
        else:
            doc.aChild(docE)
        if self.manifestType != "dependentAssembly":
            docE.setA("xmlns", "urn:schemas-microsoft-com:asm.v1")
            if self.manifestType != "assemblyBinding":
                docE.setA("manifestVersion", 
                          ".".join([str(i) for i in self.manifestVersion]))
        if self.noInheritable:
            docE.aChild(doc.cE("noInheritable"))
        if self.noInherit:
            docE.aChild(doc.cE("noInherit"))
        aId = doc.cE("assemblyIdentity")
        if self.type:
            aId.setAttribute("type", self.type)
        if self.name:
            aId.setAttribute("name", self.name)
        if self.language:
            aId.setAttribute("language", self.language)
        if self.processorArchitecture:
            aId.setAttribute("processorArchitecture", 
                             self.processorArchitecture)
        if self.version:
            aId.setAttribute("version", 
                             ".".join([str(i) for i in self.version]))
        if self.publicKeyToken:
            aId.setAttribute("publicKeyToken", self.publicKeyToken)
        if aId.hasAttributes():
            docE.aChild(aId)
        else:
            aId.unlink()
        if self.applyPublisherPolicy != None:
            ppE = doc.cE("publisherPolicy")
            ppE.setA("apply", "yes" if self.applyPublisherPolicy else "no")
            docE.aChild(ppE)
        if self.description:
            descE = doc.cE("description")
            descE.aChild(doc.cT(self.description))
            docE.aChild(descE)
        if self.requestedExecutionLevel in ("asInvoker", "highestAvailable", 
                                            "requireAdministrator"):
            tE = doc.cE("trustInfo")
            tE.setA("xmlns", "urn:schemas-microsoft-com:asm.v3")
            sE = doc.cE("security")
            rpE = doc.cE("requestedPrivileges")
            relE = doc.cE("requestedExecutionLevel")
            relE.setA("level", self.requestedExecutionLevel)
            relE.setA("uiAccess", "true" if self.uiAccess else "false")
            rpE.aChild(relE)
            sE.aChild(rpE)
            tE.aChild(sE)
            docE.aChild(tE)
        if self.dependentAssemblies:
            for assembly in self.dependentAssemblies:
                if self.manifestType != "assemblyBinding":
                    dE = doc.cE("dependency")
                    if assembly.optional:
                        dE.setAttribute("optional", "yes")
                daE = doc.cE("dependentAssembly")
                adom = assembly.todom()
                for child in adom.documentElement.childNodes:
                    daE.aChild(child.cloneNode(False))
                adom.unlink()
                if self.manifestType != "assemblyBinding":
                    dE.aChild(daE)
                    docE.aChild(dE)
                else:
                    docE.aChild(daE)
        if self.bindingRedirects:
            for bindingRedirect in self.bindingRedirects:
                brE = doc.cE("bindingRedirect")
                brE.setAttribute("oldVersion", 
                                 "-".join(".".join(str(i) for i in part) for part in bindingRedirect[0]))
                brE.setAttribute("newVersion", 
                                 ".".join(str(i) for i in bindingRedirect[1]))
                docE.aChild(brE)
        if self.files:
            for file_ in self.files:
                fE = doc.cE("file")
                for attr in ("name", "hashalg", "hash"):
                    val = getattr(file_, attr)
                    if val:
                        fE.setA(attr, val)
                docE.aChild(fE)
        return doc
    
    def toprettyxml(self, indent="  ", newl=os.linesep, encoding="UTF-8"):
        """ Return the manifest as pretty-printed XML """
        domtree = self.todom()
		# WARNING: The XML declaration has to follow the order version-encoding-standalone (standalone being optional),
		# otherwise if it is embedded in an exe the exe will fail to launch! ('application configuration incorrect')
        xmlstr = domtree.toprettyxml(indent, newl, encoding).strip(os.linesep).replace('<?xml version="1.0" encoding="UTF-8"?>', 
			'<?xml version="1.0" encoding="%s" standalone="yes"?>' % encoding)
        domtree.unlink()
        return xmlstr
    
    def toxml(self, encoding="UTF-8"):
        """ Return the manifest as XML """
        domtree = self.todom()
		# WARNING: The XML declaration has to follow the order version-encoding-standalone (standalone being optional),
		# otherwise if it is embedded in an exe the exe will fail to launch! ('application configuration incorrect')
        xmlstr = domtree.toxml(encoding).replace('<?xml version="1.0" encoding="UTF-8"?>', 
			'<?xml version="1.0" encoding="%s" standalone="yes"?>' % encoding)
        domtree.unlink()
        return xmlstr

    def update_resources(self, dstpath, names=None, languages=None):
        """ Update or add manifest to dll/exe file dstpath, as manifest 
        resource """
        UpdateManifestResourcesFromXML(dstpath, self.toprettyxml(), names, 
                                       languages)
    
    def writeprettyxml(self, filename_or_file, indent="  ", newl=os.linesep, encoding="UTF-8"):
        """ Write the manifest as XML to a file or file object """
        if isinstance(filename_or_file, (str, unicode)):
            filename_or_file = open(filename_or_file, "wb")
        xmlstr = self.toprettyxml(indent, newl, encoding)
        filename_or_file.write(xmlstr)
        filename_or_file.close()
    
    def writexml(self, filename_or_file, indent="  ", newl=os.linesep, encoding="UTF-8"):
        """ Write the manifest as XML to a file or file object """
        if isinstance(filename_or_file, (str, unicode)):
            filename_or_file = open(filename_or_file, "wb")
        xmlstr = self.toxml(indent, newl, encoding)
        filename_or_file.write(xmlstr)
        filename_or_file.close()
        
def ManifestFromResFile(filename, names=None, languages=None):
    """ Create and return manifest instance from manifest resource in 
    dll/exe file """
    res = GetManifestResources(filename, names, languages)
    if res and res[RT_MANIFEST]:
        while isinstance(res, dict) and res.keys():
            res = res[res.keys()[0]]
    if isinstance(res, dict):
        raise InvalidManifestError("No manifest resource found in '%s'" % 
                                   filename)
    manifest = ManifestFromXML(res)
    manifest.filename = filename
    return manifest
        
def ManifestFromDOM(domtree):
    """ Create and return manifest instance from DOM tree """
    manifest = Manifest()
    manifest.load_dom(domtree)
    return manifest
        
def ManifestFromXML(xmlstr):
    """ Create and return manifest instance from XML """
    manifest = Manifest()
    manifest.parse_string(xmlstr)
    return manifest
        
def ManifestFromXMLFile(filename_or_file):
    """ Create and return manifest instance from manifest file """
    manifest = Manifest()
    manifest.parse(filename_or_file)
    return manifest

def GetManifestResources(filename, names=None, languages=None):
    """ Get manifest resources from dll/exe file """
    return resource.GetResources(filename, [RT_MANIFEST], names, languages)

def UpdateManifestResourcesFromXML(dstpath, xmlstr, names=None, 
                                   languages=None):
    """ Update or add manifest XML to dll/exe file dstpath, as manifest 
    resource """
    print "I: Updating manifest in", dstpath
    name = 1 if dstpath.lower().endswith(".exe") else 2
    resource.UpdateResources(dstpath, xmlstr, RT_MANIFEST, names or [name], 
                             languages or [0, "*"])

def UpdateManifestResourcesFromXMLFile(dstpath, srcpath, names=None, 
                                       languages=None):
    """ Update or add manifest XML from file srcpath to dll/exe file 
    dstpath, as manifest resource """
    print "I: Updating manifest from", srcpath, "to", dstpath
    name = 1 if dstpath.lower().endswith(".exe") else 2
    resource.UpdateResourcesFromDataFile(dstpath, srcpath, RT_MANIFEST, 
                                         names or [name], 
                                         languages or [0, "*"])

if __name__ == "__main__":
    import sys
    
    dstpath = sys.argv[1]
    srcpath = sys.argv[2]
    UpdateManifestResourcesFromXMLFile(dstpath, srcpath)