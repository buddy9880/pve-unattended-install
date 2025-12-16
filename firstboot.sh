#!/bin/bash
curl -fsSL https://github.com/buddy9880.keys \
  >> /etc/pve/priv/authorized_keys
chmod 600 /etc/pve/priv/authorized_keys
