# Restores Object#tainted?, Object#taint, and Object#untaint
# which were removed in Ruby 3.2. Loaded via Jekyll's --require flag.

class Object
  def tainted?
    false
  end
  
  def taint
    self
  end
  
  def untaint
    self
  end
end
