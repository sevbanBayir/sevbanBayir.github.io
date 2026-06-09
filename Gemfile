# Monkey-patch Object to restore 'tainted?', 'taint', and 'untaint' which were removed in Ruby 3.2
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

source "https://rubygems.org"

gem "csv"
gem "bigdecimal"
gem "webrick"
gem "github-pages", group: :jekyll_plugins

group :jekyll_plugins do
  gem "jekyll-feed"
  gem "jekyll-seo-tag"
  gem "jekyll-paginate"
end

# Windows and JRuby does not include zoneinfo files
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

gem "wdm", "~> 0.1.1", :platforms => [:mingw, :x64_mingw, :mswin]
