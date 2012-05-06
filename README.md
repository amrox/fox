fox
===

fox is a set of tools and utilities for building iOS and Mac projects. fox is not a normal project, but rather an outlet for my deep frustrations with Apple's Xcode tools. The vision for fox to provide a complete replacement for the Xcode build and project file system (but *not* an IDE or text editor.) I realize that achieving this vision is probably impossible, but I believe I'll get something positive out of the journey.
 
**fox is very early and not recommended for production use yet.**

## Subcommands

### ipa

  * Create a signed IPA file.
 
  ```fox ipa [-h] [--project PROJECT] --target TARGET [--config CONFIG]
                 --identity IDENTITY --profile PROFILE```

	* `-h` Print help.
	* `--project` Path to Xcode profile file.
	* `--config` The build configuration. Defaults to `Debug`.
    * `--target` Refers to the name of the target in the Xcode project.
    * `--identity` Name of the code-signing identity, i.e. 'iPhone Distribution: My Company'.
    * `--profile` Provisioning profile. If a valid path is supplied, that profile is used. Also, a name can be provided, (i.e. 'MyApp Ad Hoc') and fox with search for that provisioning profile in default locations (current just `~/Library/MobileDevice/Provisioning Profiles`).


### resign

  * Resign an existing IPA file.
  
  ```fox resign [-h] --ipa IPA --identity IDENTITY --profile PROFILE
                   --output OUTPUT```
                   
    * `-h` Print help.
    * `--ipa` Path to IPA file to re-sign.
    * `--identity` Name of the code-signing identity, i.e. 'iPhone Distribution: My Company'.
    * `--profile` Provisioning profile. If a valid path is supplied, that profile is used. Also, a name can be provided, (i.e. 'MyApp Ad Hoc') and fox with search for that provisioning profile in default locations (current just `~/Library/MobileDevice/Provisioning Profiles`).
    * `---output` Path to output re-signed IPA file.
                   

# License

BSD
