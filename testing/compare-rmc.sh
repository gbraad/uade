#!/bin/bash

uade123_org=${1}
uade123_mod=${2}
mod_dir=${3}
if [[ -z "${mod_dir}" ]] ; then
    echo "Usage: $0 uade123exenotmodified uade123exemodified moddir"
    exit 1
fi
if [[ ! -x "${uade123_org}" ]] ; then
    echo "${uade123_org} is not executable"
    exit 1
fi
if [[ ! -x "${uade123_mod}" ]] ; then
    echo "${uade123_mod} is not executable"
    exit 1
fi
if [[ ! -d "${mod_dir}" ]] ; then
    echo "${mod_dir} is not a directory"
    exit 1
fi
set -e
mod_dir_org=$(mktemp -d)
mod_dir_mod=$(mktemp -d)
out_org=$(mktemp)
out_mod=$(mktemp)
cp -r "${mod_dir}" "${mod_dir_org}"
cp -r "${mod_dir}" "${mod_dir_mod}"
set +e

rmc -r "${mod_dir_org}" |grep ^meta >"${out_org}"
rmc -r "${mod_dir_mod}" |grep ^meta >"${out_mod}"

echo "Deleting temp directories"
echo
rm -rv "${mod_dir_org}" "${mod_dir_mod}"
echo

echo "Diffing rmc output in files ${out_org} and ${out_mod}"
echo
diff -u "${out_org}" "${out_mod}"
echo
echo "END OF DIFF"
