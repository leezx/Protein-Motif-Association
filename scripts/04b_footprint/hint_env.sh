#!/bin/bash

select_hint_bin() {
  local hint_env_bin=$1
  [ -x "$hint_env_bin/rgt-hint" ] || return 1
  printf '%s\n' "$hint_env_bin"
}
