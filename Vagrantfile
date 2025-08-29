Vagrant.configure("2") do |config|
    config.vm.box = "ubuntu/lunar64" # Choose an appropriate base box
  
    config.vm.network "private_network", type: "dhcp"
  
    config.vm.provider "virtualbox" do |vb|
      vb.memory = "1024" # Set the desired amount of RAM
    end
  
    config.vm.synced_folder ".", "/vagrant"
  
    config.vm.provision "shell", inline: <<-SHELL
      # Update package lists and install required packages
      apt-get update
      apt-get install -y python3 python3-pip ffmpeg unzip python3-venv
  
      # Download and unzip Bento4 binaries
      wget https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.x86_64-unknown-linux.zip
      unzip Bento4-SDK-1-6-0-635.x86_64-unknown-linux.zip
      mv Bento4-SDK-1-6-0-635.x86_64-unknown-linux/bin/* /usr/local/bin
  
      # Clean up downloaded files
      rm Bento4-SDK-1-6-0-635.x86_64-unknown-linux.zip
      rm -r Bento4-SDK-1-6-0-635.x86_64-unknown-linux
    SHELL
  end
  