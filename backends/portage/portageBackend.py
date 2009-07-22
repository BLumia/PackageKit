#!/usr/bin/python
# vim:set shiftwidth=4 tabstop=4 expandtab:
#
# Copyright (C) 2009 Mounir Lamouri (volkmar) <mounir.lamouri@gmail.com>
#
# Licensed under the GNU General Public License Version 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# packagekit imports
from packagekit.backend import *
from packagekit.progress import *
from packagekit.package import PackagekitPackage

# portage imports
# TODO: why some python app are adding try / catch around this ?
import portage
import _emerge.actions
import _emerge.stdout_spinner
import _emerge.create_depgraph_params
import _emerge.AtomArg

# layman imports
import layman.db
import layman.config

# misc imports
import sys
import signal
import re
from itertools import izip

# NOTES:
#
# Package IDs description:
# CAT/PN;PV;KEYWORD;[REPOSITORY|installed]
# Last field must be "installed" if installed. Otherwise it's the repo name
#
# Naming convention:
# cpv: category package version, the standard representation of what packagekit
#   names a package (an ebuild for portage)

# TODO:
# ERRORS with messages ?
# remove percentage(None) if percentage is used
# protection against signal when installing/removing

# Map Gentoo categories to the PackageKit group name space
CATEGORY_GROUP_MAP = {
        "app-accessibility" : GROUP_ACCESSIBILITY,
        "app-admin" : GROUP_ADMIN_TOOLS,
        "app-antivirus" : GROUP_SYSTEM,
        "app-arch" : GROUP_OTHER, # TODO
        "app-backup" : GROUP_OTHER,
        "app-benchmarks" : GROUP_OTHER,
        "app-cdr" : GROUP_OTHER,
        "app-crypt" : GROUP_OTHER,
        "app-dicts" : GROUP_OTHER,
        "app-doc" : GROUP_OTHER,
        "app-editors" : GROUP_OTHER,
        "app-emacs" : GROUP_OTHER,
        "app-emulation" : GROUP_OTHER,
        "app-forensics" : GROUP_OTHER,
        "app-i18n" : GROUP_OTHER,
        "app-laptop" : GROUP_OTHER,
        "app-misc" : GROUP_OTHER,
        "app-mobilephone" : GROUP_OTHER,
        "app-office" : GROUP_OFFICE, # DONE
        "app-pda" : GROUP_OTHER, # TODO
        "app-portage" : GROUP_OTHER,
        "app-shells" : GROUP_OTHER,
        "app-text" : GROUP_OTHER,
        "app-vim" : GROUP_OTHER,
        "app-xemacs" : GROUP_OTHER,
        "dev-ada" : GROUP_PROGRAMMING, # DONE
        "dev-cpp" : GROUP_PROGRAMMING,
        "dev-db" : GROUP_PROGRAMMING,
        "dev-dotnet" : GROUP_PROGRAMMING,
        "dev-embedded" : GROUP_PROGRAMMING,
        "dev-games" : GROUP_PROGRAMMING,
        "dev-haskell" : GROUP_PROGRAMMING,
        "dev-java" : GROUP_PROGRAMMING,
        "dev-lang" : GROUP_PROGRAMMING,
        "dev-libs" : GROUP_PROGRAMMING,
        "dev-lisp" : GROUP_PROGRAMMING,
        "dev-ml" : GROUP_PROGRAMMING,
        "dev-perl" : GROUP_PROGRAMMING,
        "dev-php" : GROUP_PROGRAMMING,
        "dev-php5" : GROUP_PROGRAMMING,
        "dev-python" : GROUP_PROGRAMMING,
        "dev-ruby" : GROUP_PROGRAMMING,
        "dev-scheme" : GROUP_PROGRAMMING,
        "dev-tcltk" : GROUP_PROGRAMMING,
        "dev-tex" : GROUP_PROGRAMMING,
        "dev-texlive" : GROUP_PROGRAMMING,
        "dev-tinyos" : GROUP_PROGRAMMING,
        "dev-util" : GROUP_PROGRAMMING,
        "games-action" : GROUP_GAMES,
        "games-arcade" : GROUP_GAMES,
        "games-board" : GROUP_GAMES,
        "games-emulation" : GROUP_GAMES,
        "games-engines" : GROUP_GAMES,
        "games-fps" : GROUP_GAMES,
        "games-kids" : GROUP_GAMES,
        "games-misc" : GROUP_GAMES,
        "games-mud" : GROUP_GAMES,
        "games-puzzle" : GROUP_GAMES,
        "games-roguelike" : GROUP_GAMES,
        "games-rpg" : GROUP_GAMES,
        "games-server" : GROUP_GAMES,
        "games-simulation" : GROUP_GAMES,
        "games-sports" : GROUP_GAMES,
        "games-strategy" : GROUP_GAMES,
        "games-util" : GROUP_GAMES,
        "gnome-base" : GROUP_DESKTOP_GNOME,
        "gnome-extra" : GROUP_DESKTOP_GNOME,
        "gnustep-apps" : GROUP_OTHER,   # TODO: from there
        "gnustep-base" : GROUP_OTHER,
        "gnustep-libs" : GROUP_OTHER,
        "gpe-base" : GROUP_OTHER,
        "gpe-utils" : GROUP_OTHER,
        "java-virtuals" : GROUP_OTHER,
        "kde-base" : GROUP_DESKTOP_KDE, # DONE from there
        "kde-misc" : GROUP_DESKTOP_KDE,
        "lxde-base" : GROUP_DESKTOP_OTHER,
        "mail-client" : GROUP_NETWORK,
        "mail-filter" : GROUP_NETWORK,
        "mail-mta" : GROUP_NETWORK,
        "media-fonts" : GROUP_FONTS,
        "media-gfx" : GROUP_GRAPHICS,
        "media-libs" : GROUP_OTHER, # TODO
        "media-plugins" : GROUP_OTHER,
        "media-radio" : GROUP_OTHER,
        "media-sound" : GROUP_OTHER,
        "media-tv" : GROUP_OTHER,
        "media-video" : GROUP_OTHER,
        "net-analyzer" : GROUP_OTHER,
        "net-dialup" : GROUP_OTHER,
        "net-dns" : GROUP_OTHER,
        "net-firewall" : GROUP_OTHER,
        "net-fs" : GROUP_OTHER,
        "net-ftp" : GROUP_OTHER,
        "net-im" : GROUP_OTHER,
        "net-irc" : GROUP_OTHER,
        "net-libs" : GROUP_OTHER,
        "net-mail" : GROUP_OTHER,
        "net-misc" : GROUP_OTHER,
        "net-nds" : GROUP_OTHER,
        "net-news" : GROUP_OTHER,
        "net-nntp" : GROUP_OTHER,
        "net-p2p" : GROUP_OTHER,
        "net-print" : GROUP_OTHER,
        "net-proxy" : GROUP_OTHER,
        "net-voip" : GROUP_OTHER,
        "net-wireless" : GROUP_OTHER,
        "net-zope" : GROUP_OTHER,
        "perl-core" : GROUP_OTHER,
        "rox-base" : GROUP_DESKTOP_OTHER, #DONE from there
        "rox-extra" : GROUP_DESKTOP_OTHER,
        "sci-astronomy" : GROUP_SCIENCE,
        "sci-biology" : GROUP_SCIENCE,
        "sci-calculators" : GROUP_SCIENCE,
        "sci-chemistry" : GROUP_SCIENCE,
        "sci-electronics" : GROUP_ELECTRONICS,
        "sci-geosciences" : GROUP_SCIENCE,
        "sci-libs" : GROUP_SCIENCE,
        "sci-mathematics" : GROUP_SCIENCE,
        "sci-misc" : GROUP_SCIENCE,
        "sci-physics" : GROUP_SCIENCE,
        "sci-visualization" : GROUP_SCIENCE,
        "sec-policy" : GROUP_SECURITY,
        "sys-apps" : GROUP_SYSTEM,
        "sys-auth" : GROUP_SYSTEM,
        "sys-block" : GROUP_SYSTEM,
        "sys-boot" : GROUP_SYSTEM,
        "sys-cluster" : GROUP_SYSTEM,
        "sys-devel" : GROUP_SYSTEM,
        "sys-freebsd" : GROUP_SYSTEM,
        "sys-fs" : GROUP_SYSTEM,
        "sys-kernel" : GROUP_SYSTEM,
        "sys-libs" : GROUP_SYSTEM,
        "sys-power" : GROUP_POWER_MANAGEMENT,
        "sys-process" : GROUP_SYSTEM,
        "virtual" : GROUP_OTHER, # TODO: what to do ?
        "www-apache" : GROUP_NETWORK,
        "www-apps" : GROUP_NETWORK,
        "www-client" : GROUP_NETWORK,
        "www-misc" : GROUP_NETWORK,
        "www-plugins" : GROUP_NETWORK,
        "www-servers" : GROUP_NETWORK,
        "x11-apps" : GROUP_OTHER, # TODO
        "x11-base" : GROUP_OTHER,
        "x11-drivers" : GROUP_OTHER,
        "x11-libs" : GROUP_OTHER,
        "x11-misc" : GROUP_OTHER,
        "x11-plugins" : GROUP_OTHER,
        "x11-proto" : GROUP_OTHER,
        "x11-terms" : GROUP_OTHER,
        "x11-themes" : GROUP_OTHER,
        "x11-wm" : GROUP_OTHER,
        "xfce-base" : GROUP_DESKTOP_XFCE, # DONE from there
        "xfce-extra" : GROUP_DESKTOP_XFCE
}


def sigquit(signum, frame):
    sys.exit(1)

def id_to_cpv(pkgid):
    '''
    Transform the package id (packagekit) to a cpv (portage)
    '''
    # TODO: raise error if ret[0] doesn't contain a '/'
    ret = split_package_id(pkgid)

    if len(ret) < 4:
        raise "id_to_cpv: package id not valid"

    # remove slot info from version field
    version = ret[1].split(':')[0]

    return ret[0] + "-" + version

def get_group(cp):
    ''' Return the group of the package
    Argument could be cp or cpv. '''
    category = portage.catsplit(cp)[0]
    if category in CATEGORY_GROUP_MAP:
        return CATEGORY_GROUP_MAP[category]

    # TODO: add message ?
    return GROUP_UNKNOWN

def get_search_list(keys):
    '''
    Get a string composed of keys (separated with spaces).
    Returns a list of compiled regular expressions.
    '''
    keys_list = keys.split(' ')
    search_list = []

    for k in keys_list:
        # not done entirely by pk-transaction
        k = re.escape(k)
        search_list.append(re.compile(k, re.IGNORECASE))

    return search_list

def is_repository_enabled(layman_db, repo_name):
    if repo_name in layman_db.overlays.keys():
        return True
    return False

class PackageKitPortageBackend(PackageKitBaseBackend, PackagekitPackage):

    def __init__(self, args, lock=True):
        signal.signal(signal.SIGQUIT, sigquit)
        PackageKitBaseBackend.__init__(self, args)

        self.portage_settings = portage.config()
        self.vardb = portage.db[portage.settings["ROOT"]]["vartree"].dbapi
        #self.portdb = portage.db[portage.settings["ROOT"]]["porttree"].dbapi

        # TODO: should be removed when using non-verbose function API
        self.orig_out = None
        self.orig_err = None

        if lock:
            self.doLock()

    # TODO: should be removed when using non-verbose function API
    def block_output(self):
        null_out = open('/dev/null', 'w')
        self.orig_out = sys.stdout
        self.orig_err = sys.stderr
        sys.stdout = null_out
        sys.stderr = null_out

    # TODO: should be removed when using non-verbose function API
    def unblock_output(self):
        sys.stdout = self.orig_out
        sys.stderr = self.orig_err

    def is_installed(self, cpv):
        if self.vardb.cpv_exists(cpv):
            return True
        return False

    def is_cpv_valid(self, cpv):
        if self.is_installed(cpv):
            # actually if is_installed return True that means cpv is in db
            return True
        elif portage.portdb.cpv_exists(cpv):
            return True

        return False

    def get_file_list(self, cpv):
        cat, pv = portage.catsplit(cpv)
        db = portage.dblink(cat, pv, portage.settings["ROOT"],
                self.portage_settings, treetype="vartree",
                vartree=self.vardb)

        contents = db.getcontents()
        if not contents:
            return []

        return db.getcontents().keys()

    def cmp_cpv(self, cpv1, cpv2):
        '''
        returns 1 if cpv1 > cpv2
        returns 0 if cpv1 = cpv2
        returns -1 if cpv1 < cpv2
        '''
        return portage.pkgcmp(portage.pkgsplit(cpv1), portage.pkgsplit(cpv2))

    def get_newest_cpv(self, cpv_list, installed):
        newer = ""

        # get the first cpv following the installed rule
        for cpv in cpv_list:
            if self.is_installed(cpv) == installed:
                newer = cpv
                break

        if newer == "":
            return ""

        for cpv in cpv_list:
            if self.is_installed(cpv) == installed:
                if self.cmp_cpv(cpv, never) == 1:
                    newer = cpv

        return newer

    def get_metadata(self, cpv, keys, in_dict = False):
        if self.is_installed(cpv):
            aux_get = self.vardb.aux_get
        else:
            aux_get = portage.portdb.aux_get

        if in_dict:
            return dict(izip(keys, aux_get(cpv, keys)))
        else:
            return aux_get(cpv, keys)

    def get_cpv_slotted(self, cpv_list):
        cpv_dict = {}

        for cpv in cpv_list:
            slot = self.get_metadata(cpv, ["SLOT"])[0]
            if slot not in cpv_dict:
                cpv_dict[slot] = [cpv]
            else:
                cpv_dict[slot].append(cpv)

        return cpv_dict

    def filter_free(self, cpv_list, fltlist):
        if len(cpv_list) == 0:
            return cpv_list

        def _has_validLicense(cpv):
            metadata = self.get_metadata(cpv, ["LICENSE", "USE", "SLOT"], True)
            return not self.portage_settings._getMissingLicenses(cpv, metadata)

        if FILTER_FREE in fltlist or FILTER_NOT_FREE in fltlist:
            free_licenses = "@FSF-APPROVED"
            if FILTER_FREE in fltlist:
                licenses = "-* " + free_licenses
            else:
                licenses = "* -" + free_licenses
            backup_license = self.portage_settings["ACCEPT_LICENSE"]
            self.portage_settings["ACCEPT_LICENSE"] = licenses
            self.portage_settings.backup_changes("ACCEPT_LICENSE")
            self.portage_settings.regenerate()

            cpv_list = filter(_has_validLicense, cpv_list)

            self.portage_settings["ACCEPT_LICENSE"] = backup_license
            self.portage_settings.backup_changes("ACCEPT_LICENSE")
            self.portage_settings.regenerate()

        return cpv_list

    def filter_newest(self, cpv_list, fltlist):
        if len(cpv_list) == 0:
            return cpv_list

        if FILTER_NEWEST not in fltlist:
            return cpv_list

        if FILTER_INSTALLED in fltlist:
            # we have one package per slot, so it's the newest
            return cpv_list

        cpv_dict = self.get_cpv_slotted(cpv_list)

        # slots are sorted (dict), revert them to have newest slots first
        slots = cpv_dict.keys()
        slots.reverse()

        # empty cpv_list, cpv are now in cpv_dict and cpv_list gonna be repop
        cpv_list = []

        for k in slots:
            # if not_intalled on, no need to check for newest installed
            if FILTER_NOT_INSTALLED not in fltlist:
                newest_installed = self.get_newest_cpv(cpv_dict[k], True)
                if newest_installed != "":
                    cpv_list.append(newest_installed)
            newest_available = self.get_newest_cpv(cpv_dict[k], False)
            if newest_available != "":
                cpv_list.append(newest_available)

        return cpv_list

    def get_all_cp(self, fltlist):
        # NOTES:
        # returns a list of cp
        #
        # FILTERS:
        # - installed: ok
        # - free: ok (should be done with cpv)
        # - newest: ok (should be finished with cpv)
        cp_list = []

        if FILTER_INSTALLED in fltlist:
            cp_list = self.vardb.cp_all()
        elif FILTER_NOT_INSTALLED in fltlist:
            cp_list = portage.portdb.cp_all()
        else:
            # need installed packages first
            cp_list = self.vardb.cp_all()
            for cp in portage.portdb.cp_all():
                if cp not in cp_list:
                    cp_list.append(cp)

        return cp_list

    def get_all_cpv(self, cp, fltlist, filter_newest=True):
        # NOTES:
        # returns a list of cpv
        #
        # FILTERS:
        # - installed: ok
        # - free: ok
        # - newest: ok

        cpv_list = []

        # populate cpv_list taking care of installed filter
        if FILTER_INSTALLED in fltlist:
            cpv_list = self.vardb.match(cp)
        elif FILTER_NOT_INSTALLED in fltlist:
            for cpv in portage.portdb.match(cp):
                if not self.is_installed(cpv):
                    cpv_list.append(cpv)
        else:
            cpv_list = self.vardb.match(cp)
            for cpv in portage.portdb.match(cp):
                if cpv not in cpv_list:
                    cpv_list.append(cpv)

        # free filter
        cpv_list = self.filter_free(cpv_list, fltlist)

        # newest filter
        if filter_newest:
            cpv_list = self.filter_newest(cpv_list, fltlist)

        return cpv_list

    def cpv_to_id(self, cpv):
        '''
        Transform the cpv (portage) to a package id (packagekit)
        '''
        package, version, rev = portage.pkgsplit(cpv)
        pkg_keywords, repo, slot = self.get_metadata(cpv,
                ["KEYWORDS", "repository", "SLOT"])

        pkg_keywords = pkg_keywords.split()
        sys_keywords = self.portage_settings["ACCEPT_KEYWORDS"].split()
        keywords = []

        for x in sys_keywords:
            if x in pkg_keywords:
                keywords.append(x)

        # if no keywords, check in package.keywords
        if not keywords:
            key_dict = self.portage_settings.pkeywordsdict.get(portage.dep_getkey(cpv))
            if key_dict:
                for _, keys in key_dict.iteritems():
                    for x in keys:
                        keywords.append(x)

        if not keywords:
            keywords.append("no keywords")
            self.message(MESSAGE_UNKNOWN, "No keywords have been found for %s" % cpv)

        # don't want to see -r0
        if rev != "r0":
            version = version + "-" + rev
        # add slot info if slot != 0
        if slot != '0':
            version = version + ':' + slot

        # if installed, repo should be 'installed', packagekit rule
        if self.is_installed(cpv):
            repo = "installed"

        return get_package_id(package, version, ' '.join(keywords), repo)

    def get_packages_required(self, cpv_input, settings, trees, recursive):
        '''
        Get a list of cpv, portage settings and tree and recursive parameter
        And returns the list of packages required for cpv list
        '''
        # TODO: should see if some cpv in the input list is not a dep of another
        packages_list = []

        myopts = {}
        myopts["--selective"] = True
        myopts["--deep"] = True

        myparams = _emerge.create_depgraph_params.create_depgraph_params(
                myopts, "remove")
        depgraph = _emerge.depgraph.depgraph(settings, trees, myopts,
                myparams, None)

        # TODO: atm, using FILTER_INSTALLED because it's quicker
        # and we don't want to manage non-installed packages
        for cp in self.get_all_cp([FILTER_INSTALLED]):
            for cpv in self.get_all_cpv(cp, [FILTER_INSTALLED]):
                depgraph._dynamic_config._dep_stack.append(
                        _emerge.Dependency.Dependency(
                            atom=portage.dep.Atom('=' + cpv),
                            root=portage.settings["ROOT"], parent=None))

        if not depgraph._complete_graph():
            self.error(ERROR_INTERNAL_ERROR, "Error when generating depgraph")
            return

        def _add_children_to_list(packages_list, node):
            for n in depgraph._dynamic_config.digraph.parent_nodes(node):
                if n not in packages_list \
                        and not isinstance(n, _emerge.SetArg.SetArg):
                    packages_list.append(n)
                    _add_children_to_list(packages_list, n)

        for node in depgraph._dynamic_config.digraph.__iter__():
            if isinstance(node, _emerge.SetArg.SetArg):
                continue
            if node.cpv in cpv_input:
                if recursive:
                    _add_children_to_list(packages_list, node)
                else:
                    for n in \
                            depgraph._dynamic_config.digraph.parent_nodes(node):
                        if not isinstance(n, _emerge.SetArg.SetArg):
                            packages_list.append(n)

        return packages_list

    def package(self, cpv, info=None):
        desc = self.get_metadata(cpv, ["DESCRIPTION"])[0]
        if not info:
            if self.is_installed(cpv):
                info = INFO_INSTALLED
            else:
                info = INFO_AVAILABLE
        PackageKitBaseBackend.package(self, self.cpv_to_id(cpv), info, desc)

    def get_depends(self, filters, pkgs, recursive):
        # TODO: use only myparams ?
        # TODO: improve error management / info

        # FILTERS:
        # - installed: ok
        # - free: ok
        # - newest: ignored because only one version of a package is installed

        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(None)

        fltlist = filters.split(';')

        cpv_input = []
        cpv_list = []

        for pkg in pkgs:
            cpv = id_to_cpv(pkg)
            if not self.is_cpv_valid(cpv):
                self.error(ERROR_PACKAGE_NOT_FOUND,
                        "Package %s was not found" % pkg)
                continue
            cpv_input.append('=' + cpv)

        myopts = {}
        myopts["--selective"] = True
        myopts["--deep"] = True
        settings, trees, _ = _emerge.actions.load_emerge_config()
        myparams = _emerge.create_depgraph_params.create_depgraph_params(
                myopts, "")

        depgraph = _emerge.depgraph.depgraph(
                settings, trees, myopts, myparams, None)
        retval, fav = depgraph.select_files(cpv_input)

        if not retval:
            self.error(ERROR_INTERNAL_ERROR,
                    "Wasn't able to get dependency graph")
            return

        def _add_children_to_list(cpv_list, node):
            for n in depgraph._dynamic_config.digraph.child_nodes(node):
                if n not in cpv_list:
                    cpv_list.append(n)
                    _add_children_to_list(cpv_list, n)

        for cpv in cpv_input:
            for r in depgraph._dynamic_config.digraph.root_nodes():
                # TODO: remove things with @ as first char
                # TODO: or refuse SetArgs
                if not isinstance(r, _emerge.AtomArg.AtomArg):
                    continue
                if r.atom == cpv:
                    if recursive:
                        _add_children_to_list(cpv_list, r)
                    else:
                        for n in \
                                depgraph._dynamic_config.digraph.child_nodes(r):
                            for c in \
                                depgraph._dynamic_config.digraph.child_nodes(n):
                                cpv_list.append(c)

        def _filter_uninstall(cpv):
            return cpv[3] != 'uninstall'
        def _filter_installed(cpv):
            return cpv[0] == 'installed'
        def _filter_not_installed(cpv):
            return cpv[0] != 'installed'

        # removing packages going to be uninstalled
        cpv_list = filter(_filter_uninstall, cpv_list)

        # install filter
        if FILTER_INSTALLED in fltlist:
            cpv_list = filter(_filter_installed, cpv_list)
        if FILTER_NOT_INSTALLED in fltlist:
            cpv_list = filter(_filter_not_installed, cpv_list)

        # now we can change cpv_list to a real cpv list
        tmp_list = cpv_list[:]
        cpv_list = []
        for x in tmp_list:
            cpv_list.append(x[2])
        del tmp_list

        # free filter
        cpv_list = self.filter_free(cpv_list, fltlist)

        for cpv in cpv_list:
            # prevent showing input packages
            if '=' + cpv not in cpv_input:
                self.package(cpv)

    def get_details(self, pkgs):
        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(0)

        nb_pkg = float(len(pkgs))
        pkg_processed = 0.0

        def get_size(cpv):
            # should return package size if not installed
            # or 0 if installed
            if self.is_installed(cpv):
                return 0
            ebuild = portage.portdb.findname(cpv)
            if not ebuild: # should probably not happen
                return 0
            dir = os.path.dirname(ebuild)
            manifest = portage.manifest.Manifest(dir,
                    portage.settings["DISTDIR"])
            uris = portage.portdb.getFetchMap(cpv)
            return manifest.getDistfilesSize(uris)

        for pkg in pkgs:
            cpv = id_to_cpv(pkg)

            if not self.is_cpv_valid(cpv):
                self.error(ERROR_PACKAGE_NOT_FOUND,
                        "Package %s was not found" % pkg)
                continue

            homepage, desc, license = self.get_metadata(cpv,
                    ["HOMEPAGE", "DESCRIPTION", "LICENSE"])

            self.details(self.cpv_to_id(cpv), license, get_group(cpv),
                    desc, homepage, get_size(cpv))

            pkg_processed += 100.0
            self.percentage(int(pkg_processed/nb_pkg))

        self.percentage(100)

    def get_files(self, pkgs):
        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(0)

        nb_pkg = float(len(pkgs))
        pkg_processed = 0.0

        for pkg in pkgs:
            cpv = id_to_cpv(pkg)

            if not self.is_cpv_valid(cpv):
                self.error(ERROR_PACKAGE_NOT_FOUND,
                        "Package %s was not found" % pkg)
                continue

            if not self.is_installed(cpv):
                self.error(ERROR_CANNOT_GET_FILELIST,
                        "get-files is only available for installed packages")
                continue

            files = self.get_file_list(cpv)
            files = sorted(files)
            files = ";".join(files)

            self.files(pkg, files)

            pkg_processed += 100.0
            self.percentage(int(pkg_processed/nb_pkg))

        self.percentage(100)

    def get_packages(self, filters):
        self.status(STATUS_QUERY)
        self.allow_cancel(True)
        self.percentage(0)

        fltlist = filters.split(';')
        cp_list = self.get_all_cp(fltlist)
        nb_cp = float(len(cp_list))
        cp_processed = 0.0

        for cp in self.get_all_cp(fltlist):
            for cpv in self.get_all_cpv(cp, fltlist):
                self.package(cpv)

            cp_processed += 100.0
            self.percentage(int(cp_processed/nb_cp))

        self.percentage(100)

    def get_repo_list(self, filters):
        # NOTES:
        # use layman API
        # returns only official and supported repositories
        # and creates a dummy repo for portage tree
        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(None)

        fltlist = filters.split(';')

        # get installed and available dbs
        installed_layman_db = layman.db.DB(layman.config.Config())
        available_layman_db = layman.db.RemoteDB(layman.config.Config())

        # 'gentoo' is a dummy repo
        self.repo_detail('gentoo', 'Gentoo Portage tree', True)

        if FILTER_DEVELOPMENT in fltlist:
            for o in available_layman_db.overlays.keys():
                if available_layman_db.overlays[o].is_official() \
                        and available_layman_db.overlays[o].is_supported():
                    self.repo_detail(o,
                            available_layman_db.overlays[o].description,
                            is_repository_enabled(installed_layman_db, o))

    def get_requires(self, filters, pkgs, recursive):
        # TODO: manage non-installed package

        # FILTERS:
        # - installed: error atm, see previous TODO
        # - free: ok
        # - newest: ignored because only one version of a package is installed

        self.status(STATUS_RUNNING)
        self.allow_cancel(True)
        self.percentage(None)

        fltlist = filters.split(';')

        cpv_input = []
        cpv_list = []

        if FILTER_NOT_INSTALLED in fltlist:
            self.error(ERROR_CANNOT_GET_REQUIRES,
                    "get-requires returns only installed packages at the moment")
            return

        for pkg in pkgs:
            cpv = id_to_cpv(pkg)

            if not self.is_cpv_valid(cpv):
                self.error(ERROR_PACKAGE_NOT_FOUND,
                        "Package %s was not found" % pkg)
                continue
            if not self.is_installed(cpv):
                self.error(ERROR_CANNOT_GET_REQUIRES,
                        "get-requires is only available for installed packages at the moment")
                continue

            cpv_input.append(cpv)

        settings, trees, _ = _emerge.actions.load_emerge_config()

        packages_list = self.get_packages_required(cpv_input,
                settings, trees, recursive)

        # now we can populate cpv_list
        cpv_list = []
        for p in packages_list:
            cpv_list.append(p.cpv)
        del packages_list

        # free filter
        cpv_list = self.filter_free(cpv_list, fltlist)

        for cpv in cpv_list:
            # prevent showing input packages
            if '=' + cpv not in cpv_input:
                self.package(cpv)

    def get_update_detail(self, pkgs):
        # TODO: a lot of informations are missing

        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(None)

        for pkg in pkgs:
            updates = []
            obsoletes = ""
            vendor_url = ""
            bugzilla_url = ""
            cve_url = ""

            cpv = id_to_cpv(pkg)

            if not portage.portdb.cpv_exists(cpv):
                self.message(MESSAGE_COULD_NOT_FIND_PACKAGE, "could not find %s" % pkg)

            for cpv in self.vardb.match(portage.pkgsplit(cpv)[0]):
                updates.append(cpv)
            updates = "&".join(updates)

            # temporarily set vendor_url = homepage
            homepage = self.get_metadata(cpv, ["HOMEPAGE"])[0]
            vendor_url = homepage

            self.update_detail(pkg, updates, obsoletes, vendor_url, bugzilla_url,
                    cve_url, "none", "No update text", "No ChangeLog",
                    UPDATE_STATE_STABLE, None, None)

    def get_updates(self, filters):
        # NOTES:
        # because of a lot of things related to Gentoo,
        # only world and system packages are can be listed as updates
        # _except_ for security updates

        # UPDATE TYPES:
        # - blocked: wait for feedbacks
        # - low: TODO: --newuse
        # - normal: default
        # - important: none atm
        # - security: from @security

        # FILTERS:
        # - installed: try to update non-installed packages and call me ;)
        # - free: ok
        # - newest: ok

        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(None)

        fltlist = filters.split(';')

        settings, trees, _ = _emerge.actions.load_emerge_config()
        root_config = trees[self.portage_settings["ROOT"]]["root_config"]

        update_candidates = []
        cpv_updates = {}
        cpv_downgra = {}

        # get system and world packages
        for s in ["system", "world"]:
            set = portage.sets.base.InternalPackageSet(
                    initial_atoms=root_config.setconfig.getSetAtoms(s))
            for atom in set:
                update_candidates.append(atom.cp)

        # check if a candidate can be updated
        for cp in update_candidates:
            cpv_list_inst = self.vardb.match(cp)
            cpv_list_avai = portage.portdb.match(cp)

            cpv_dict_inst = self.get_cpv_slotted(cpv_list_inst)
            cpv_dict_avai = self.get_cpv_slotted(cpv_list_avai)

            dict_upda = {}
            dict_down = {}

            # candidate slots are installed slots
            slots = cpv_dict_inst.keys()
            slots.reverse()

            for s in slots:
                cpv_list_updates = []
                cpv_inst = cpv_dict_inst[s][0] # only one install per slot

                # the slot can be outdated (not in the tree)
                if s not in cpv_dict_avai:
                    break

                tmp_list_avai = cpv_dict_avai[s]
                tmp_list_avai.reverse()

                for cpv in tmp_list_avai:
                    if self.cmp_cpv(cpv_inst, cpv) == -1:
                        cpv_list_updates.append(cpv)
                    else: # because the list is sorted
                        break

                # no update for this slot
                if len(cpv_list_updates) == 0:
                    if [cpv_inst] == portage.portdb.visible([cpv_inst]):
                        break # really no update
                    else:
                        # that's actually a downgrade or even worst
                        if len(tmp_list_avai) == 0:
                            break # this package is not known in the tree...
                        else:
                            dict_down[s] = [tmp_list_avai.pop()]

                cpv_list_updates = self.filter_free(cpv_list_updates, fltlist)

                if len(cpv_list_updates) == 0:
                    break

                if FILTER_NEWEST in fltlist:
                    best_cpv = portage.best(cpv_list_updates)
                    cpv_list_updates = [best_cpv]

                dict_upda[s] = cpv_list_updates

            if len(dict_upda) != 0:
                cpv_updates[cp] = dict_upda
            if len(dict_down) != 0:
                cpv_downgra[cp] = dict_down

        # get security updates
        for atom in portage.sets.base.InternalPackageSet(
                initial_atoms=root_config.setconfig.getSetAtoms("security")):
            # send update message and remove atom from cpv_updates
            if atom.cp in cpv_updates:
                slot = self.get_metadata(atom.cpv, ["SLOT"])[0]
                if slot in cpv_updates[atom.cp]:
                    tmp_cpv_list = cpv_updates[atom.cp][slot][:]
                    for cpv in tmp_cpv_list:
                        if self.cmp_cpv(cpv, atom.cpv) >= 0:
                            # cpv is a security update and removed from list
                            cpv_updates[atom.cp][slot].remove(cpv)
                            self.package(cpv, INFO_SECURITY)
            else: # update also non-world and non-system packages if security
                self.package(atom.cpv, INFO_SECURITY)

        # downgrades
        for cp in cpv_downgra:
            for slot in cpv_downgra[cp]:
                for cpv in cpv_downgra[cp][slot]:
                    self.package(cpv, INFO_IMPORTANT)

        # normal updates
        for cp in cpv_updates:
            for slot in cpv_updates[cp]:
                for cpv in cpv_updates[cp][slot]:
                    self.package(cpv, INFO_NORMAL)

    def install_packages(self, only_trusted, pkgs):
        self.status(STATUS_RUNNING)
        self.allow_cancel(True) # TODO: sure ?
        self.percentage(None)

        # FIXME: use only_trusted

        for pkg in pkgs:
            # check for installed is not mandatory as there are a lot of reason
            # to re-install a package (USE/{LD,C}FLAGS change for example) (or live)
            # TODO: keep a final position
            cpv = id_to_cpv(pkg)

            # is cpv valid
            if not portage.portdb.cpv_exists(cpv):
                self.error(ERROR_PACKAGE_NOT_FOUND, "Package %s was not found" % pkg)
                continue

            # inits
            myopts = {} # TODO: --nodepends ?
            spinner = ""
            favorites = []
            settings, trees, mtimedb = _emerge.load_emerge_config()
            myparams = _emerge.create_depgraph_params(myopts, "")
            spinner = _emerge.stdout_spinner()

            depgraph = _emerge.depgraph(settings, trees, myopts, myparams, spinner)
            retval, favorites = depgraph.select_files(["="+cpv])
            if not retval:
                self.error(ERROR_INTERNAL_ERROR, "Wasn't able to get dependency graph")
                continue

            if "resume" in mtimedb and \
            "mergelist" in mtimedb["resume"] and \
            len(mtimedb["resume"]["mergelist"]) > 1:
                mtimedb["resume_backup"] = mtimedb["resume"]
                del mtimedb["resume"]
                mtimedb.commit()

            mtimedb["resume"] = {}
            mtimedb["resume"]["myopts"] = myopts.copy()
            mtimedb["resume"]["favorites"] = [str(x) for x in favorites]

            # TODO: check for writing access before calling merge ?

            mergetask = _emerge.Scheduler(settings, trees, mtimedb,
                    myopts, spinner, depgraph.altlist(),
                    favorites, depgraph.schedulerGraph())
            mergetask.merge()

    def refresh_cache(self, force):
        # NOTES: can't manage progress even if it could be better
        # TODO: do not wait for exception, check timestamp
        # TODO: message if overlay repo has changed (layman)
        self.status(STATUS_REFRESH_CACHE)
        self.allow_cancel(True)
        self.percentage(None)

        myopts = {'--quiet': True}
        settings, trees, mtimedb = _emerge.actions.load_emerge_config()

        # get installed and available dbs
        installed_layman_db = layman.db.DB(layman.config.Config())

        if force:
            timestamp_path = os.path.join(
                    settings["PORTDIR"], "metadata", "timestamp.chk")
            if os.access(timestamp_path, os.F_OK):
                os.remove(timestamp_path)

        try:
            self.block_output()
            for o in installed_layman_db.overlays.keys():
                installed_layman_db.sync(o, True)
            _emerge.actions.action_sync(settings, trees, mtimedb, myopts, "")
            self.unblock_output()
        except:
            self.unblock_output()
            self.error(ERROR_INTERNAL_ERROR, traceback.format_exc())

    def remove_packages(self, allowdep, autoremove, pkgs):
        # TODO: implement allowdep
        # can't use allowdep: never removing dep

        self.status(STATUS_RUNNING)
        self.allow_cancel(True)
        self.percentage(None)

        cpv_list = []
        packages = []

        settings, trees, mtimedb = _emerge.actions.load_emerge_config()
        root_config = trees[self.portage_settings["ROOT"]]["root_config"]

        # create cpv_list
        for pkg in pkgs:
            cpv = id_to_cpv(pkg)

            if not self.is_cpv_valid(cpv):
                self.error(ERROR_PACKAGE_NOT_FOUND,
                        "Package %s was not found" % pkg)
                continue

            if not self.is_installed(cpv):
                self.error(ERROR_PACKAGE_NOT_INSTALLED,
                        "Package %s is not installed" % pkg)
                continue

            cpv_list.append(cpv)

        # backend do not implement autoremove
        if autoremove:
            self.message(MESSAGE_AUTOREMOVE_IGNORED,
                    "Portage backend do not implement autoremove option")

        # create packages list
        db_keys = list(portage.portdb._aux_cache_keys)
        for cpv in cpv_list:
            metadata = self.get_metadata(cpv, db_keys, in_dict=True)
            package = _emerge.Package.Package(
                    type_name="ebuild",
                    built=True,
                    installed=True,
                    root_config=root_config,
                    cpv=cpv,
                    metadata=metadata,
                    operation="uninstall")
            packages.append(package)
        del db_keys

        # now, we can remove
        try:
            self.block_output()
            mergetask = _emerge.Scheduler.Scheduler(settings,
                    trees, mtimedb, mergelist=packages, myopts={},
                    spinner=None, favorites=[], digraph=None)
            mergetask.merge()
        finally:
            self.unblock_output()

    def repo_enable(self, repoid, enable):
        # NOTES: use layman API >= 1.2.3
        self.status(STATUS_INFO)
        self.allow_cancel(True)
        self.percentage(None)

        # special case: trying to work with gentoo repo
        if repoid == 'gentoo':
            if not enable:
                self.error(ERROR_CANNOT_DISABLE_REPOSITORY,
                        "gentoo repository can't be disabled")
            return

        # get installed and available dbs
        installed_layman_db = layman.db.DB(layman.config.Config())
        available_layman_db = layman.db.RemoteDB(layman.config.Config())

        # check now for repoid so we don't have to do it after
        if not repoid in available_layman_db.overlays.keys():
            self.error(ERROR_REPO_NOT_FOUND,
                    "Repository %s was not found" % repoid)
            return

        # disabling (removing) a db
        # if repository already disabled, ignoring
        if not enable and is_repository_enabled(installed_layman_db, repoid):
            try:
                installed_layman_db.delete(installed_layman_db.select(repoid))
            except Exception, e:
                self.error(ERROR_INTERNAL_ERROR,
                        "Failed to disable repository "+repoid+" : "+str(e))
                return

        # enabling (adding) a db
        # if repository already enabled, ignoring
        if enable and not is_repository_enabled(installed_layman_db, repoid):
            try:
                # TODO: clean the trick to prevent outputs from layman
                self.block_output()
                installed_layman_db.add(available_layman_db.select(repoid),
                        quiet=True)
                self.unblock_output()
            except Exception, e:
                self.unblock_output()
                self.error(ERROR_INTERNAL_ERROR,
                        "Failed to enable repository "+repoid+" : "+str(e))
                return

    def resolve(self, filters, pkgs):
        self.status(STATUS_QUERY)
        self.allow_cancel(True)
        self.percentage(0)

        fltlist = filters.split(';')
        cp_list = self.get_all_cp(fltlist)
        nb_cp = float(len(cp_list))
        cp_processed = 0.0

        reg_expr = []
        for pkg in pkgs:
            reg_expr.append("^" + re.escape(pkg) + "$")
        reg_expr = "|".join(reg_expr)

        # specifications says "be case sensitive"
        s = re.compile(reg_expr)

        for cp in cp_list:
            if s.match(cp):
                for cpv in self.get_all_cpv(cp, fltlist):
                    self.package(cpv)

            cp_processed += 100.0
            self.percentage(int(cp_processed/nb_cp))

        self.percentage(100)

    def search_details(self, filters, keys):
        # NOTES: very bad performance
        self.status(STATUS_QUERY)
        self.allow_cancel(True)
        self.percentage(0)

        fltlist = filters.split(';')
        cp_list = self.get_all_cp(fltlist)
        nb_cp = float(len(cp_list))
        cp_processed = 0.0
        search_list = get_search_list(keys)

        for cp in cp_list:
            # unfortunatelly, everything is related to cpv, not cp
            # can't filter cp
            cpv_list = []

            # newest filter can't be executed now
            # because some cpv are going to be filtered by search conditions
            # and newest filter could be alterated
            for cpv in self.get_all_cpv(cp, fltlist, filter_newest=False):
                match = True
                details = self.get_metadata(cpv,
                        ["DESCRIPTION", "HOMEPAGE","LICENSE","repository"])
                for s in search_list:
                    found = False
                    for x in details:
                        if s.search(x):
                            found = True
                            break
                    if not found:
                        match = False
                        break
                if match:
                    cpv_list.append(cpv)

            # newest filter
            cpv_list = self.filter_newest(cpv_list, fltlist)

            for cpv in cpv_list:
                self.package(cpv)

            cp_processed += 100.0
            self.percentage(int(cp_processed/nb_cp))

        self.percentage(100)

    def search_file(self, filters, key):
        # FILTERS:
        # - ~installed is not accepted (error)
        # - free: ok
        # - newest: as only installed, by himself
        self.status(STATUS_QUERY)
        self.allow_cancel(True)
        self.percentage(0)

        fltlist = filters.split(';')

        if FILTER_NOT_INSTALLED in fltlist:
            self.error(ERROR_CANNOT_GET_FILELIST,
                    "search-file isn't available with ~installed filter")
            return

        cpv_list = self.vardb.cpv_all()
        nb_cpv = 0.0
        cpv_processed = 0.0
        is_full_path = True

        if key[0] != "/":
            is_full_path = False
            key = re.escape(key)
            searchre = re.compile("/" + key + "$", re.IGNORECASE)

        # free filter
        cpv_list = self.filter_free(cpv_list, fltlist)
        nb_cpv = float(len(cpv_list))

        for cpv in cpv_list:
            for f in self.get_file_list(cpv):
                if (is_full_path and key == f) \
                or (not is_full_path and searchre.search(f)):
                    self.package(cpv)

            cpv_processed += 100.0
            self.percentage(int(cpv_processed/nb_cpv))

        self.percentage(100)

    def search_group(self, filters, group):
        # TODO: filter unknown groups before searching ? (optimization)
        self.status(STATUS_QUERY)
        self.allow_cancel(True)
        self.percentage(0)

        fltlist = filters.split(';')
        cp_list = self.get_all_cp(fltlist)
        nb_cp = float(len(cp_list))
        cp_processed = 0.0

        for cp in cp_list:
            if get_group(cp) == group:
                for cpv in self.get_all_cpv(cp, fltlist):
                    self.package(cpv)

            cp_processed += 100.0
            self.percentage(int(cp_processed/nb_cp))

        self.percentage(100)

    def search_name(self, filters, keys):
        # NOTES: searching in package name, excluding category
        # TODO: search for cat/pkg if '/' is found
        self.status(STATUS_QUERY)
        self.allow_cancel(True)
        self.percentage(0)

        fltlist = filters.split(';')
        cp_list = self.get_all_cp(fltlist)
        nb_cp = float(len(cp_list))
        cp_processed = 0.0
        search_list = get_search_list(keys)

        for cp in cp_list:
            # pkg name has to correspond to _every_ keys
            pkg_name = portage.catsplit(cp)[1]
            found = True
            for s in search_list:
                if not s.search(pkg_name):
                    found = False
                    break
            if found:
                for cpv in self.get_all_cpv(cp, fltlist):
                    self.package(cpv)

            cp_processed += 100.0
            self.percentage(int(cp_processed/nb_cp))

        self.percentage(100)

    def update_packages(self, only_trusted, pkgs):
        # TODO: add some checks ?
        self.install_packages(only_trusted, pkgs)

    def update_system(self, only_trusted):
        # TODO: only_trusted
        self.status(STATUS_RUNNING)
        self.allow_cancel(True)
        self.percentage(None)

        # inits
        myopts = {}
        myopts.pop("--deep", None)
        myopts.pop("--newuse", None)
        myopts.pop("--update", None)
        myopts["--deep"] = True
        myopts["--newuse"] = True
        myopts["--update"] = True

        spinner = ""
        favorites = []
        settings, trees, mtimedb = _emerge.load_emerge_config()
        myparams = _emerge.create_depgraph_params(myopts, "")
        spinner = _emerge.stdout_spinner()

        depgraph = _emerge.depgraph(settings, trees, myopts, myparams, spinner)
        retval, favorites = depgraph.select_files(["system", "world"])
        if not retval:
            self.error(ERROR_INTERNAL_ERROR, "Wasn't able to get dependency graph")
            return

        if "resume" in mtimedb and \
        "mergelist" in mtimedb["resume"] and \
        len(mtimedb["resume"]["mergelist"]) > 1:
            mtimedb["resume_backup"] = mtimedb["resume"]
            del mtimedb["resume"]
            mtimedb.commit()

        mtimedb["resume"] = {}
        mtimedb["resume"]["myopts"] = myopts.copy()
        mtimedb["resume"]["favorites"] = [str(x) for x in favorites]

        mergetask = _emerge.Scheduler(settings, trees, mtimedb,
                myopts, spinner, depgraph.altlist(),
                favorites, depgraph.schedulerGraph())
        mergetask.merge()

def main():
    backend = PackageKitPortageBackend("") #'', lock=True)
    backend.dispatcher(sys.argv[1:])

if __name__ == "__main__":
    main()
