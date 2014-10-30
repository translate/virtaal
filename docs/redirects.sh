#!/bin/bash

extension=".rst"

product=$1
shift 1
files=$*

echo "# Automatically generated - please review each redirect"
for file in $files
do
	base_filename=$(basename $file $extension)
	wikifile=/wiki/$product/$base_filename
	rtdfile=http://docs.translatehouse.org/projects/$product/en/latest/${base_filename}.html
	printf "Redirect Permanent %-40s%s\n" ${wikifile} ${rtdfile}
done
