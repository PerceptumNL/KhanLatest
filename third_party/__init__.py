"""Set up pythonpath correctly for third-party files.

Here's some necessary background, using agar/ as an example:

We don't want to just have people import from the agar source directly
in third_party, because due to the way the agar directory tree is set
up, to import from it you'd need to do
   import third_party.agar.agar
rather than just
   import third_party.agar
(this is because we don't install agar via 'pip install' or the like,
but instead just use the source directly).

Even without that problem, agar code internally does
   import agar.foo.bar
which would fail normally, since we put agar under third_party.agar,
not agar.

Instead we install the source under agar-src (using a - instead of a _
so people can't import from it accidentally), and have a symlink from
agar to agar-src/agar.  That allows
   import third_party.agar.foo.bar
and all is happy.

Except the agar package itself isn't happy, because code in there has
   import agar.foo.bar
and that needs to work.  This file fixes that up by adjusting the
sys.path so it *does* work.  It also adds a tricky import hook to
ensure that nobody makes use of this new sys.path functionality
except for code in third_party -- 'normal' Khan Academy files
need to do import third_party.agar.boo.bar instead.
"""

import os
import sys
import traceback


# Allow agar code to import internal libraries via import agar.foo.bar.
# Note it will be able to import other third-party libraries without
# needing the third_party prefix as well -- that's a feature!
_third_party_root = os.path.dirname(__file__)
sys.path.insert(0, _third_party_root)


# Disallow other code from importing agar libararies via import agar.foo.bar
# This fancy technique is based on ideas in
# http://journal.thobe.org/2008/07/simple-stuff-with-import-hooks-in.html

class ThirdPartyRestrictedImport(object):
    """If you import agar.whatever, make sure you live in third_party."""
    def find_module(self, module_name, package_path):
        """Return an error-yielding object if the import is bad, else None.

        The way import hooks work, if find_module() returns an object
        that defines load_module(), that object will be used to load
        the module.  If instead we return None, the standard import
        mechanism will be used.

        In this case, we return None if the import is ok -- it's not
        an import of a restricted module, or if it is the import is
        coming from third_party.  We return self otherwise.
        self.load_module will then raise an exception, disallowing the
        import.

        Args:
          module_name: what we're trying to import
          package_path: the parent directory of the module_name, or None
        """
        # It's a bit unclear to me how module_name and package_path
        # work, but experimentation indicates that module-name only
        # ever starts with 'agar', say, if the text is literally
        # 'import agar' or 'import agar.whatever'.  So this check
        # gives the ok to 'import third_party.agar'.
        module_root = module_name.split('.', 1)[0]
        if not os.path.exists(os.path.join(_third_party_root, module_root)):
            # They're not trying to import something under third-party.
            return None

        # tb[0] is our caller, the import statement (tb[1] is us).
        caller = traceback.extract_stack(limit=2)[0]
        caller_file = caller[0]
        # Importers in third_party can refer to modules however they want.
        # TODO(csilvers): better would be to split the filename components
        # and check if any is third_party, but this is probably good enough.
        if 'third_party' in caller_file:
            return None

        # Other importers must follow the rules!
        return self

    def load_module(self, module_name):
       raise ImportError('You must import %s via "import third_party.%s"'
                         % (module_name, module_name))


sys.meta_path.append(ThirdPartyRestrictedImport())
