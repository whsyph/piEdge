local mp = require 'mp'
local utils = require 'mp.utils'

function on_file_loaded()
    -- Path on the Pi
    local path = "/home/pi/museum_signage/public/audio_config.json"
    local f = io.open(path, "r")
    if not f then
        -- Fallback to local path for testing
        path = "public/audio_config.json"
        f = io.open(path, "r")
    end
    
    if not f then
        mp.msg.warn("Could not find audio_config.json")
        return
    end
    
    local content = f:read("*all")
    f:close()
    
    -- Retrieve screen index (1 or 2) passed from script-opts
    local screen = mp.get_opt("screen") or "1"
    local filename = mp.get_property("filename")
    
    if not filename then return end
    
    -- Extract the JSON section for our specific screen using balanced braces match %b{}
    local screen_section = content:match('"screen' .. screen .. '"%s*:%s*(%b{})')
    if not screen_section then
        mp.msg.warn("Could not find screen" .. screen .. " section in config")
        return
    end
    
    -- Check if global mute is active
    local global_mute = screen_section:match('"global_mute"%s*:%s*(%a+)') == "true"
    
    -- Check if the current filename has a custom clip setting
    local escaped_fn = filename:gsub("[%-%.%+%*%?%[%]%^%$%(%)%%]", "%%%1")
    local clip_mute = false
    
    local clip_match = screen_section:match('"' .. escaped_fn .. '"%s*:%s*(%b{})')
    if clip_match then
        clip_mute = clip_match:match('"mute"%s*:%s*(%a+)') == "true"
    end
    
    -- Check channel mode setting and apply panning filters
    local channel_mode = screen_section:match('"channel_mode"%s*:%s*"([^"]+)"') or "stereo"
    local af_filter = ""
    if channel_mode == "left" then
        af_filter = "lavfi=[pan=stereo|c0=c0|c1=0]"
    elseif channel_mode == "right" then
        af_filter = "lavfi=[pan=stereo|c0=0|c1=c1]"
    end
    mp.set_property("af", af_filter)
    
    -- Apply final mute state to player
    local final_mute = global_mute or clip_mute
    mp.set_property_bool("mute", final_mute)
    
    mp.msg.info(string.format(
        "File: %s | Screen: %s | Global Mute: %s | Clip Mute: %s | Channel Mode: %s | Final: %s",
        filename, screen, tostring(global_mute), tostring(clip_mute), channel_mode, tostring(final_mute)
    ))
end

-- Hook into file-loaded event to apply mute settings instantly when video changes
mp.register_event("file-loaded", on_file_loaded)
