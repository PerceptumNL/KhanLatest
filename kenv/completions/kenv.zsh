if [[ ! -o interactive ]]; then
    return
fi

compctl -K _kenv kenv

_kenv() {
  local word words completions
  read -cA words
  word="${words[2]}"

  if [ "${#words}" -eq 2 ]; then
    completions="$(kenv commands)"
  else
    completions="$(kenv completions "${word}")"
  fi

  reply=("${(ps:\n:)completions}")
}
