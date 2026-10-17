#!/usr/bin/env bash
# 一键部署到 Ubuntu/Debian（需 root）。用法： sudo bash deploy/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=/opt/gallery
apt-get install -y nginx python3 >/dev/null
mkdir -p $DEST/state
cp server.py $DEST/
# 已有数据时不覆盖 data.json / settings.json / 图片
if [ -f $DEST/www/data.json ]; then
  rsync -a --exclude data.json --exclude settings.json --exclude img --exclude thumb www/ $DEST/www/ 2>/dev/null || \
  (cd www && tar cf - --exclude=./data.json --exclude=./settings.json --exclude=./img --exclude=./thumb . | tar xf - -C $DEST/www)
else
  cp -r www $DEST/
fi
if [ ! -f $DEST/.env ]; then
  cp .env.example $DEST/.env
  sed -i "s/replace-with-random-hex/$(openssl rand -hex 32)/" $DEST/.env
  echo ">> 请编辑 $DEST/.env 设置访客密码和后台密码，然后 systemctl restart gallery"
fi
chown -R www-data:www-data $DEST/www $DEST/state
chmod 600 $DEST/.env
cp deploy/gallery.service /etc/systemd/system/gallery.service
cp deploy/nginx.conf /etc/nginx/sites-available/gallery
ln -sf /etc/nginx/sites-available/gallery /etc/nginx/sites-enabled/gallery
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload && systemctl enable --now gallery && systemctl restart gallery
nginx -t && systemctl reload nginx
echo ">> 完成：http://<服务器IP>/   后台：/admin"
