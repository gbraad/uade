#!/bin/bash

dname=$1
if [[ -z ${dname} ]] ; then
    echo "Give directory of hipc songs"
    exit 1
fi

mkdir -p synth
find "${dname}" -type f |while read fname ; do
    echo "Synthesizing $fname"
    bname=$(basename "${fname}")
    for player in hipc newhipc ; do
	uade123 -f "synth/${bname}_${player}.wav" -P "${player}" "${fname}"
    done
done
