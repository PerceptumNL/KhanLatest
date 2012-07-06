import os


# provides full path to files in packages
def resolve_files(default_path, packages, suffix):
    for package_name in packages:
        package = packages[package_name]

        package_path = package.get("base_path")
        if not package_path:
            dir_name = "%s-package" % package_name
            package_path = os.path.join(default_path, dir_name)

        package_path = os.path.join(os.path.dirname(__file__), package_path)
        package_path = os.path.normpath(package_path)

        # Get a list of all files in the package.
        files = package.get("files", [])
        if not files:
            raise "No files found in package %s" % package_name

        yield (package_name, package_path, files)
