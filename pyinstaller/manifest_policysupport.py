#!/usr/bin/env python

from manifest import *

def __find_files(self):
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
        policies = os.path.join(winsxs, "Policies")
        version = self.version
        # in Windows XP and 2003, Policies is an extra dir with subdirs
        # containing *.policy files.
        # in Vista and later, Policies are *.manifest files inside the
        # Manifests dir.
        if not os.path.isdir(policies):
            # Vista or later
            policies = manifests
        if os.path.isdir(policies):
            policy_re = re.compile(('%s_policy\.%s\.%s\.+%s_%s_' + ('.*\.manifest' if policies == manifests else '')) % 
                                   (re.escape(self.processorArchitecture), 
                                    self.version[0], # major
                                    self.version[1], # minor
                                    re.escape(self.name), 
                                    re.escape(self.publicKeyToken)), re.I)
            redirect = False
            for nm in os.listdir(policies):
                policynm = os.path.join(policies, nm)
                if policy_re.match(nm) and ((policies == manifests and os.path.isfile(policynm)) or (policies != manifests and os.path.isdir(policynm))):
                    for fn in ([policynm] if policies == manifests else os.listdir(policynm)):
                        if policies != manifests and not fn.lower().endswith(".policy"):
                            continue
                        manifestnm = policynm if policies == manifests else os.path.join(policynm, fn)
                        try:
                            policy = ManifestFromXMLFile(manifestnm)
                        except Exception, exc:
                            print "E:", manifestnm, str(exc)
                            pass
                        else:
                            print "I: Checking policy for binding redirects:", manifestnm
                            for assembly in policy.dependentAssemblies:
                                if assembly.optional:
                                    continue
                                for bindingRedirect in assembly.bindingRedirects:
                                    print "I: Checking binding redirect:", bindingRedirect
                                    if version >= bindingRedirect[0][0] and \
                                       version <= bindingRedirect[0][-1]:
                                        print "I: Binding redirect:", version, "->",
                                        version = bindingRedirect[1]
                                        print version
                                        if policy.version == self.version:
                                            redirect = True
                                            break
                                if redirect:
                                    break
                        if redirect:
                            break
        if os.path.isdir(manifests):
            assembly_re = re.compile('%s_%s_%s_%s_.*\.manifest' % 
                                     (re.escape(self.processorArchitecture), 
                                      re.escape(self.name), 
                                      re.escape(self.publicKeyToken), 
                                      re.escape(".".join([str(i) for i in version]))), re.I)
            for nm in os.listdir(manifests):
                if assembly_re.match(nm):
                    manifestnm = os.path.join(manifests, nm)
                    assemblynm = os.path.splitext(nm)[0]
                    if not os.path.isfile(manifestnm):
                        print "W: No such file", manifestnm, "part of assembly", assemblynm
                        continue
                    print "I: Found manifest", manifestnm
                    assemblydir = os.path.join(winsxs, assemblynm)
                    if not os.path.isdir(assemblydir):
                        print "W: No such dir", assemblydir
                        continue
                    try:
                        manifest = ManifestFromXMLFile(manifestnm)
                    except Exception, exc:
                        print "E:", manifestnm, str(exc)
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
                            files.append(manifestnm)
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
            manifestnm = os.path.join(path, assemblynm + ext)
            if not os.path.isfile(manifestnm):
                print "W: No such file", manifestnm, "part of assembly", assemblynm
                continue
            print "I: Found manifest", manifestnm
            try:
                if ext == ".dll":
                    manifest = ManifestFromResFile(manifestnm, [1])
                else:
                    manifest = ManifestFromXMLFile(manifestnm)
            except Exception, exc:
                print "E:", manifestnm, str(exc)
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
                files.append(manifestnm)
                files.extend(rfiles)
            break
        if not os.path.isfile(manifestnm):
            for file_ in self.files:
                fn = os.path.join(path, file_.name)
                if os.path.exists(fn):
                    # if any of our files does exist without the manifest 
                    # in the same dir, the assembly is incomplete
                    return []
    return files

Manifest.find_files = __find_files
