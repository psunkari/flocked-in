#
# Copy the latest source from "incoming" to "deploy"
# and restart the application
#

cur_dir=`pwd` && cd $HOME

if [ -f deploy/twistd.pid ]; then
  pid=`cat deploy/twistd.pid` && kill $pid
fi

del_older=(public scripts social social.tac templates twisted)
mv_newer=(public scripts social social.tac templates twisted)

if [ ! -d deploy ]; then
  if [ -a deploy ]; then
    mv deploy deploy.old
  fi
  mkdir deploy;
fi

# Remove older files
for name in ${del_older[*]}; do
  rm -rf deploy/$name
done

# Copy new files
for name in ${mv_newer[*]}; do
  mv source/$name deploy/
done

# Copy updated default configurations
cp -a source/etc/* deploy/etc/

# Start twisted daemon
cd deploy && twistd -y social.tac
cd $cur_dir
