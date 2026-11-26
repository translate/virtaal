#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Fail unless every leg of the named CI jobs succeeded.

A matrix job's combined `needs.<job>.result` can be `success` while one
of its legs was cancelled, e.g. a leg no runner picked up. Endpoint jobs
read each leg's own conclusion from the jobs API instead:

    gh api "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/jobs?filter=latest&per_page=100" \\
        --paginate > jobs.json
    python3 check_job_legs.py jobs.json test-macos build-macos-app

A job's legs are the jobs named JOB or "JOB (...)". A job with no legs
in the run fails too."""

import json
import sys


def load_jobs(text):
    """Jobs from the API's response pages, a jobs list or one job per line."""
    decoder = json.JSONDecoder()
    jobs = []
    pos = 0
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos == len(text):
            return jobs
        value, pos = decoder.raw_decode(text, pos)
        if isinstance(value, dict) and 'jobs' in value:
            jobs.extend(value['jobs'])
        elif isinstance(value, list):
            jobs.extend(value)
        else:
            jobs.append(value)


def legs(jobs, name):
    return [job for job in jobs
            if job['name'] == name or job['name'].startswith(name + ' (')]


def problems(jobs, names):
    """One message per named job with no legs or a leg that didn't succeed."""
    found = []
    for name in names:
        matched = legs(jobs, name)
        if not matched:
            found.append('%s: no jobs in this run' % name)
        for job in matched:
            if job.get('conclusion') != 'success':
                found.append('%s: %s' % (job['name'], job.get('conclusion') or job.get('status')))
    return found


def main(argv):
    if len(argv) < 3:
        print('usage: check_job_legs.py JOBS_JSON JOB [JOB ...]', file=sys.stderr)
        return 2
    with open(argv[1], encoding='utf-8') as f:
        jobs = load_jobs(f.read())
    found = problems(jobs, argv[2:])
    for message in found:
        print('::error::%s' % message)
    if not found:
        print('All legs of %s succeeded.' % ', '.join(argv[2:]))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
