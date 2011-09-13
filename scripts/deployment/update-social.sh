#
# Copy the latest source from "incoming" to "deploy"
# and restart the application
#

cur_dir=`pwd` && cd $HOME
pid=`cat social/twistd.pid` && kill $pid

del_older=(public scripts social social.tac templates twisted)
mv_newer=(public scripts social social.tac templates twisted)

if [ ! -d deploy ]; then
  if [ -a deploy ]; then
    mv deploy deploy.old
  fi
  mkdir deploy;
fi

for name in ${del_older[*]}; do
  rm -rf deploy/$name
done

for name in ${mv_newer[*]}; do
  mv source/$name deploy/
done

cd deploy && twistd -y social.tac
cd $cur_dir
