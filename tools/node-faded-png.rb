require "chunky_png"

Dir["../images/node-*.png"].each do |f|

  next if f =~ /-faded\.png$/

  puts f
  image = ChunkyPNG::Image.from_file(f)

  for y in 0...image.height do
    for x in 0...image.width do
      c = image.get_pixel(x, y)
      c = (c & ~0xff) | ((c & 0xff) * 0.4).to_i
      if c & 0xff != 0
        c = ChunkyPNG::Color.compose(c, ChunkyPNG::Color::BLACK)
      end
      image.set_pixel(x, y, c)
    end
  end

  image.save(f.gsub(/\.png$/, "-faded.png"))

end
