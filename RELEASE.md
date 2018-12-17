# Release Process

# Release a new version
1. Make sure that version.py has the new version on master
1. Create a new release in github using master branch, includes release notes.
1. Check the travis job: https://travis-ci.org/eventbrite/bay
1. Check the new version on pypi: https://pypi.python.org/pypi/bay/

# Release a hot fix
1. Create the branch from the current version tag
1. Patch the fix to that branch (that branch will not be merged)
1. Bump the version.py (last digit)
1. Create a new release in github using the new branch
1. Create a github PR to apply the fix to master, without bumping the version.py
