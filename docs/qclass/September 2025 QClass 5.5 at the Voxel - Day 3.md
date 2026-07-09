# September 2025 QClass 5.5 at the Voxel - Day 3

Source transcript: `September 2025 QClass 5.5 at the Voxel - Day 3.txt`

Preshow
14:06
Do it. Stream time. Class time. Woohoo.
Welcome
14:19
All right, folks. Good morning. Welcome back to  day three, this third and final day of QClass. Um,
14:27
today we're going to talk about lighting. We're  going to talk about QLab collaboration. We're
14:32
going to talk about uh QLab Remote. A small  topic, but a valuable one. And then we're
14:39
also going to talk about workflow tools uh which  are all uh it's our catchall name for a series
14:46
of tools inside QLab which are aimed at helping  you use QLab productively and effectively which
14:53
aren't necessarily audience visible or audible.  We'll talk about scripting as much as people have
14:59
uh an appetite for. And um all of those topics  add up to most of a full day. So there's plenty
15:06
of room to sort of let the class drive the  agenda today. So um as I have been saying,
15:14
please don't be shy about raising your hand and  and uh and trying to guide the discussion into
15:21
the corner of your interest. That's perfectly okay  and in fact wonderful. um and particularly this
15:29
afternoon where we have a lot of space for that  or comparatively a lot of space. Okay, without
Intro to Lighting - DMX, Art-net, interfaces
15:34
further ado, introduction to lighting. Okay, we've  all heard of lighting. It's very important. Um I
15:43
believe it came in the beginning in fact to many  people. Uh not not all. Um my favorite creation
15:51
myth begins in the beginning there was nothing but  water and two ducks. um which is a particular
15:57
Native American creation myth which I truly truly  love and it just for me feels like it can start
16:05
however you like. Water and two ducks is as good a  start as any. Um, lighting, uh, which has existed
16:13
for an enormously long percentage of the time that  people have been doing theater, um, really sort of
16:21
entered into the chat for QLab in QLab 4. um and  has uh been by design progressing slowly as we
16:34
um recognize that QLab is uh in the world of audio  kind of um was when it started in a more wide
16:44
open field. But when we started with lighting,  there were a lot of other folks doing lighting control in a quite established way. And we have  been building QLab's lighting tools slowly while
16:55
trying to get as much information from people who  use QLab for lighting. What is it that you use QLab
17:01
for lighting for? What are you doing? How are you  doing it? What do you need? What do you want? So,
17:08
we've been building these tools slowly and we  are right now entering into the beginning of a
17:13
phase of more intense focus on that subject. So,  what I'm about to show you today is what QLab can
17:20
currently do. But I think that it's worth pointing  out that now is perhaps among the best time to
17:28
let us know how you feel about the next steps we  should take because we're about to take them. Um,
17:36
QLab interacts with the physical world of lighting  using um two mechanisms. Um to start with there
17:44
is Art-net and then after that there are a small  number of uh compatible USB DMX devices. Um just
17:53
to make sure we're all starting on the same page,  DMX which uh stands for digital multiplex
18:01
which starts with X as we all know. Digital  multiplexing. This was a lighting control
18:08
standard developed um throughout the 80s and early  90s and I think it was ratified in like 1991,
18:14
maybe 1990 as the way that we're going to  communicate between lighting control devices
18:19
and lighting devices. Mostly at that time it was  dimmer but also scrollers and moving mirrors and
18:25
then moving lights. And um now many if not most of  our lighting fixtures in me in in lots of theaters
18:32
are LED fixtures which take DMX straight to the  fixture and uh the DMX signal tells the fixture
18:41
what to do and when. Right. And the great thing  about DMX is that it is fairly stupid. It is um
18:48
a signal that moves at uh about 40 I think 44  hertz and 44 times a second it just spits out a
18:56
series of 512 numbers. There are 512 channels in  a universe of DMX and 44 times a second it says
19:05
channel one is at 5%, channel 2 is at 12%, channel  3 is at 100%. Although it doesn't actually say
19:11
percent, it says a value between 0 and 255. That's  not actually that important right now. When you
19:19
see one DMX cable which has five pins on it like  a MIDI cable and like a MIDI cable, two of those
19:25
pins don't do anything. Uh that is that one cable  carries one universe of DMX. A universe of DMX
19:33
is 512 channels. If you need 514 channels on your  show, you need a second universe. Um, if you look
19:44
at the back of a traditional lighting console, you  will see one or more five pin DMX sockets and one
19:51
um, most of the consoles can be configured.  You can tell the sockets, socket number one, you send the first universe, socket number two,  you send the second universe. But you could also
20:03
say both sockets send one universe. so that I can  send some DMX over there, some DMX over there, and
20:08
channels, you know, 1 through 12 are over there,  and channels 20 through 30 are over there. And
20:13
it's convenient physically to send two different  cables. The reason I'm jabbering on about this is
20:19
because the physical distribution of DMX around a  venue has become complicated since we moved away
20:26
from a stack of dimmer in a room and then running  cable from the dimmer to lights, which got dimmed
20:32
by the dimmer. Now we've got stuff all around the  theater that wants a DMX cable coming straight
20:37
into it. So the physical distribution of DMX is a  bit of a hassle compared to how it was. Partly in
20:46
response to this, some clever folks invented  something called Art-net. Art-net is DMX on an
20:54
Ethernet network. And they thought, okay, DMX  is a fairly dumb signal. It's just a bunch of
21:01
text going not that fast. We could packetize  it and make it Ethernet traffic and then the
21:08
Ethernet network which already runs throughout the  building could be co-opted to transmit DMX data.
21:14
And on the one hand that's great. On the other  hand, if you have lots of DMX traffic, it can
21:19
overwhelm that network and take over for it. which  is why streaming ACN came along, which does the
21:26
same thing but a little bit more comfortably with  friends. It's a less of a bully uh with network
21:32
traffic. QLab does not use streaming ACN right now.  If that's something you think is important to you,
21:38
I'd love to hear about it. Um we use Art-net for a  couple of reasons. The first is we were confident
21:45
with the knowledge that is provided by the folks  who invented Art-net we were confident that we could implement it well inside QLab and reliably  which we're pretty confident we have done. The
21:55
other reason is there are lots of folks out there  who make Art-net decoders which receive Ethernet
22:02
traffic and produce five pin DMX outputs or 3 pin  but DMX on the traditional DMX cabling. And it's
22:12
nice that there are lots of manufacturers because  we can say if you've got QLab and you want DMX,
22:20
get any Art-net node. They're often called nodes.  Get any Art-net node and it'll basically work.
22:28
Largely that's true. Although I'm here to tell  you that if you buy nodes that are made by NTEC
22:34
and DMX King and um um ETC, you're likely to have  the best time in my opinion. Now, I'm sure there
22:44
are other people out there who have a great time  with other nodes, and I'm not I'm not going to poo poo anyone. Um, the only thing I want to point  out is if the manufacturer of your Art-net node
22:56
is not a company with their own website and their  own downloadable manuals, it's going to be harder
23:01
to troubleshoot your problems. And there are a  handful of manufacturers in mostly in Europe and
23:08
Asia that are well marketed and well sold, but you  can never figure out who actually made the thing.
23:15
And maybe a lot of the time that's no problem.  But if you need help, it's nice to be able to
23:21
say this website belongs to the company that made  the thing I bought. I can download the manual from them or I can call them or I can email them or I  can contact them in some way. Again, your mileage
23:32
will vary. You should do what makes uh what what  works for you. For me, DMX King specifically,
23:39
first of all, they're from New Zealand,  which makes them friendly. Um, second of all,
23:45
they are responsive in their customer service.  And third of all, their products have that magical combination of being well-built and inexpensive.  So, it's very hard to argue with that. Um,
23:56
that said, any Art-net node will work with QLab.  Okay. The other possibility for interfacing QLab
24:06
with your lights is a USB DMX decoder. And we have  a limited set of USB DMX devices that we support.
24:16
It is [Music] that's the list. The NEC DMX USB Pro  and USB Pro Mark II, the DMX King UltraDMX series,
24:27
the DMX King EDMX series, and the Yarilo DMX Pro.  Yarilo is a Russian company that lobbied very hard
24:35
for us to support them. And as soon as we finished  and verified support, they went out of business.
24:41
They're still on the list, though. And if you want  one and you find one, it'll work. I have one. It's
24:48
fine. It's perfectly fine. Um, DMX, uh, Enttech  also makes something called the open DMX or the
24:57
USB open. I can't remember exactly the name of it.  It's a very inexpensive USB device. Crucially, QLab
25:03
does not support that device. That device is meant  for tinkering uh at the hardware level with DMX.
25:09
It's not meant for real Showtime use. It's not  optically isolated, which means that if there's an electrical problem in your lights, it will  become an electrical problem in your Mac really
25:18
quickly. So, that doesn't work. It did exactly  this list for USB devices. If you find a USB DMX
25:27
device that you really think we ought to support,  I'd love to hear about it. Please let us know.
25:32
um we may not be able to support it or we may  choose not to support it if we learn things about it that means we think it's a bad fit but  I'd still like to hear about it. So these connect
25:45
directly to a Mac via USB and they provide an  uh an DMX uh connection. Some of them have one,
25:53
some of them have two, and some of them have  four universes of DMX. Art-net devices connect
25:59
to a network. So if your Mac is on a network as  this one is and the Art-net nodes are also on the
26:07
network as we have the physical distribution  of DMX doesn't matter uh vis a vis where the Mac
26:17
is physically in the building right if I had USB  DMX adapters on this thing I would have to drag
26:24
those those DMX cables to this desk to plug into  my lights but as it is I don't have to do that.
26:32
That the installation of these lights and the  distribution of DMX cabling is independent of
26:39
where the MAC is physically. So that's kind of  the big advantage. The other big advantage is
26:44
that an Ethernet network that's doing nothing  but Art-net is capable of carrying something in
26:50
the neighborhood of 16.5 million channels of  DMX, i.e. should be enough. The Art-net spec is
27:02
kind of complicated. It says, "Okay, we have nets,  subnets, and universes. Each subnet contains
27:13
some number of universes, and each net contains  some number of subnets." We'll get to that in a little while, but it in short, it basically says  if you plug one network connection into your Mac,
27:22
you have address you have access to a fantastic  number of DMX channels. So that's the other
27:30
reason Art-net's nice. It's it's it grows with  you. Okay. Now that I've sort of talked about the
27:35
physical side, which is important and necessary,  but um, I found that if I start to teach lighting
27:40
and don't mention that first, people are like,  "Yeah, but I've got a Mac. How does it plug into
27:45
my lights? I don't even understand what you're  talking about until you talk about that." So, I wanted to gloss over that quickly. Now, we'll  talk about how QLab does lights, understanding
27:53
that that physical side does happen. We'll get  back to it in greater detail in a short time.
Basics of the Light cue and the Light Dashboard
28:01
In lighting uh in QLab, the uh you  interact with lighting through two
28:06
basic components. The light cue which is a type  of cue which works basically like a fade cue and
28:14
the light dashboard which is a window  which you get to under the window menu. The light dashboard is a set of controls which  show you and let you modify the current state of
28:27
lights in your system. So right now there are 1,  two, 3, four, five, six lights that are controlled
28:35
by QLab that are on at the moment. Right? I have  named them VX 1 through six. There's a VX7 there
28:45
which is for putting a splash of color on here  when there's no projection. VX short for Voxel. So
28:55
um the dashboard lets me select those lights.  The sidebar of the dashboard lets me see if uh if
29:02
those lights have such parameters. Let me see the  color parameter of the light. I also have a moving
29:10
light which is not turned on right now. There's  a Mac um what is it? A Maverick. Yeah, not a
29:18
not a Mac. There's a Maverick up there. Uh Rogue  Maverick. Um it's got uh color changing and it's
29:25
also got pan and tilt controls. So those appear  here in the sidebar when that light is selected.
29:32
So I can do simple control of the  lights like this. I've dimmed them out,
29:40
brought them back. I can open this up and  look at all of the parameters of the light.
29:48
So I can either adjust individual  channels like red, lime, amber, green,
29:53
etc. intensity or I can use the color control  here in the sidebar to adjust the color of the
30:00
selected light. If I select multiple lights,  I can adjust all of their color at once.
30:10
And now we have a nice orange, right?
30:18
So that's the basic interaction with lights.  Live control here. cues live here like any other
30:24
cue in QLab. A light cue which has the basics tab  which you all know about and the triggers tab
30:30
which you all know about. And the curve tab  which we talked about a little bit with fade cues also has the levels tab. The levels tab  contains the light commands, as we call it,
30:44
that tell QLab to do stuff with lights when you run  the cue. So, this light cue sets lights 12, 13,
30:53
15, and 14. Yes, they're out of order, to these  values. The yellow line on these sliders shows
31:03
the current level of those lights. The slider and  the numerical value here shows the level that the
31:10
lights will go to when I run the cue. So when  I run this cue, both here and in the dashboard,
31:19
we see 12, 13, 14, and 15 fade live from where  they were to here. The triangle arrow head on
31:30
the slider shows the the direction that the  level changed most recently. So things that
31:38
went up most recently have an upward pointing  to the right arrow. Things that went down most
31:44
recently have a right pointing arrow. And controls  with a circular handle were not recently moved.
31:58
The values here in the levels tab of a lighting  cue, a light cue can be shown either as sliders,
32:06
as tiles in which the yellow borders intensity is
32:13
analogous to the intensity of the value or  as text which is editable as regular text.
32:25
There's some other controls here which we're going to work our way through as  we talk about lighting. Yeah,
32:32
there's at the top of the levels tab a command  line which also exists at the top of the
32:38
dashboard which lets you control lights. Here  it lets you control lights live by typing. So,
32:45
I can say things like 12 through 15 at zero. And  that happens. I don't have lights 12 through 15
32:55
hung right now, so you won't see that happen.  I'm deliberately choosing to control lights that are not up right now so that doing stuff  fast and furious in the dashboard doesn't make
33:07
it harder to see what's happening, right? We'll  do some demos with the lights that are actually
33:12
live because that's what we're here for. But  I want to just sort of talk about how to use these tools without it becoming a visual assault.  The command line in the cue tab and the levels tab
33:26
of the cue here is used for adding commands to  the cue. So if I want to add 16 to this light cue,
33:36
I can say 16 at 45%. When I hit enter, it gets  added to the list of commands in that light
33:42
cue. If I don't feel if I don't, if typing is  not my preferred interaction, I can also choose
33:49
add command and I get a hierarchical menu of  all the lights and light groups, which we'll
33:55
talk about. And when I hover over a light, I see  all of the parameters that belong to that light.
34:04
So I can say yes 13 I want to change  its hue and now I've added 13 hue to
34:12
my command list and I can go adjust  that to some number. You did I hope
34:20
notice that there were times where I just  wrote an individual I just wrote a number 13
34:28
at 10. But here when I added hue, it says 13.  Hue. QLab has uh a syntax of name of light with
34:41
a dot and then name of parameter. And that's the  syntax for how we address a parameter. So if a
34:49
light has red, green, blue, and intensity, we can  say light. To address its red value, light.blue to
34:58
address its blue value, light.intensity Intensity  will address its intensity value, but also light
35:04
without any dot or suffix will address what we  call its default parameter, which for most lights
35:09
is intensity. The default parameter is baked  into the definition of the light. You don't have
35:14
to worry about it. But that's what lets you just  say, put those lights at 50. We all know that when
35:21
someone says that, what we mean is the brightness  of the light. But that's that's a cultural thing,
35:26
right? That's colloquial. If you have a light  that has no brightness, what's a light with no
35:31
brightness? Well, it's not really a light. It's  a DMX controlled other thing like maybe a smoke machine or a fan. It's not appropriate for the  smoke machine to have an intensity control be
35:42
because perhaps that means brightness and  brightness is there's no brightness of the smoke machine. So maybe we say smoke machine  at full. What we want is the smoke the smoke
35:52
volume to be at full or maybe what we want is the  fan speed to be at full. So different parameters
35:58
can be the default parameter for different types  of fixtures. Does that make sense? Okay, great.
Light cue philosophy - sparse cues and collation
36:08
Something that I think is sort of the most  significant unusual thing about QLab lighting
36:14
compared to other lighting controllers is  that light cues are um what we call sparse.
36:26
And what that means is that light cues  only contain commands for the lights that
36:32
they contain commands for and they have  no effect on other lights. So I don't
36:38
know if this demo is exactly set up to work  right with the current plot. No, it's not.
36:48
Give me just a second. For this demo, I'm going  to briefly um let's put the lights back on. What's
36:59
going on here is I have a demonstration of a  series of cues that address lights 11, 12, 13,
37:04
14, and 15. The lights that I actually have in the  theater are called VX1 2 3 4 and 5. And I would
37:12
like to use these for my demo. So, I'm going  to go and skip ahead in this lesson briefly.
Re-arranging the light patch for the sparse cue demo
37:21
Not going to spend too much time explaining  every little thing I'm doing because I want to get to this demo first, but it will give you  a preview of adjusting the light patch. I'm
37:32
going to go into workspace settings, light, light  patch. I'm going to delete lights 11 through 15,
37:47
which don't do anything because they're not  actually here in the theater. command delete.
37:53
All of these cues which contain commands for  11 through 15 are now broken. Right? Hey,
37:59
I'm talking to a light and it's gone. I will say  fear not little lights because I'm going to rename
38:07
these lights 11. And it ask QLab asked me, hey,  all the cues that already talk to VX1, do you
38:15
want to update those cues to now talk to its new  name? I could say no. leave them alone. I'm going
38:21
to rename it back to VX1 later or I'm going to  read a new light and call that VX1. But here,
38:27
I'm going to say yes, update those light cues.  So, every light cue which previously addressed the
38:32
light called VX1 now addresses that same actual  light by its new name, which is 11. To make this
38:43
even clearer, I'm going to get rid of all these  other lights that are not part of this demo.
38:52
VX2 is going to become 12, and I'm going to  update light cues. VX3 is going to become 13,
38:59
updating light cues. VX4 will become 14, updating  cues. VX5 becomes 15, updating cues. VX6 becomes
39:06
16, updating cues. and VX7 becomes 17 updating  cues. So my patch now contains lights 11 through
39:15
17 which are these same seven fixtures going  by a new name inside QLab. And all the cues
39:23
which used to address those seven fixtures still  address those seven fixtures just by a new name.
39:30
And all the light cues that were broken because  they talked to lights 11 through 17 are now no
39:36
longer broken because 11 through 17 now exist.  And those light cues that were sitting here
39:42
wishing they could speak to lights 11 through  17, yay, my wish has been fulfilled. Right.
39:59
Okay, we're going to talk more about the light  patch in detail later, but I wanted to give
40:04
you that quick um demonstration. Okay, light  cues in QLab are sparse. What that means here,
The sparse cue demo
40:14
I'm going to uh show you a sort of quick  um and dirty cue sheet which describes what's
40:21
going on while the lights do the same thing.  They're not actually connected. I made this by
40:26
hand. Does that make sense? Okay, great. When  we start when we boot up our lighting system,
40:34
when we arrive in the morning, everything's  off. So, the starting point uh for our day is
40:40
all five of those fixtures have an intensity at  0%. And our live levels indeed say zero. when I
40:46
hit light Q1 and light Q1 here is uh sets  11 to 100, 12 to 100, and 13 to 100. Oops.
41:04
Uh, and now I of course made a little  mistake because these fixtures need a color.
41:15
So now 11, 12, and 13 are at 100%.
41:21
14, 15, 16, and 17 stay out because they  receive no instructions. Light Q2 brings
41:30
14 to 30% and 15 to 50%. 16 and 17 still  nothing. 1 2 and three stayed at 100%. Why?
41:42
light Q2 did not tell them to do anything.
41:49
When I run light Q3, like Q3 brings 12 to 10%.  And indeed, my center fixture is now down at 10%.
41:58
All it did was bring 12 to 10.  The other fixtures are left alone.
42:07
Light Q4 brings channel 11, fixture 11 to  80%. Our live values are now 80 10 1350.
42:20
If I just run light Q2 out of context, light Q2  just brings 14 and 15 to 30 and 50. And you see in
42:32
the dashboard here they are at 30 and 50. Although  I think I accidentally yeah reset their color. I
42:41
just ran light Q2. It doesn't bring up 1 through  3 even though 1 through 3 are at 100% before light
42:49
Q2 because unlike a console that does tracking  most letting consoles QLab does not by default
43:00
assume that running a cue out of order means hey  pretend we ran all the cues before this cue. I have
43:09
nothing against tracking consoles. I think it's  brilliant. I prefer it to non-tracking consoles.
43:15
I, this guy, who admittedly is not a full-time  lighting designer, prefer QLab's approach. I like
43:22
saying this cue affects these lights only, and  when I run this cue, only these lights change.
Collation (making QLab behave like a regular tracking console)
43:31
But many people, many completely  put together and reasonable people,
43:36
many experts at lighting design  say, "Okay, that's insane though
43:41
because here's what happens. Sometimes we  rehearse the show starting at scene two, and there was stuff in scene one that set  me up for scene two. So when I run light Q2,
43:52
I would really like light Q1 to have run in the  past, right?" Completely logical desire. And as
44:01
a result, we have an attribute in a lighting cue  called collate. A light cue that is set to collate.
44:15
When you run it, it will look up in the cue list,  the same cue list, up the list all the way to the
44:22
top and look at every light cue. Imagine that they  ran collate the effects of them having run include
44:33
that collated result into itself and then go and  because this is just plain numbers it does that
44:41
very fast. It does it in zero human time. It takes  some amount of computer time but those time that
44:49
very small amount. If you are running a show,  a traditional theatrical show, it may be wise
44:59
to have the default posture be all light cues are  set to collate. And then on an individual basis,
45:05
you can tell light cues, no, you don't collate.  I did a show in high school. For whatever reason,
45:12
this really stuck with me. No, middle school. I  was in middle school running lights for this. This I think probably stuck with me because I think  it's the first time I ran lights. And I was in
45:20
front of the console which we called Darth Vader.  because it was large and grumpy and black and
45:25
sparks shot out of it and um it was not a great  piece of equipment and yet they put children in
45:33
front of it. Um and it had to be respected and  it could choke you. No. Um uh Darth Vader was a
45:40
two scene preset. So I had a row of 18 faders here  and a row of 18 faders here and then a cross fader
45:46
here. When the cross fader was up, whatever these  faders were doing is what the dimmers were doing.
45:52
When the cross fader was down, whatever these  faders were doing was what the dimmer were doing. We had a scene that took place in a hotel room in  a cheap hotel. So, we were up in the top scene and
46:01
the lights were like so. And the lighting designer  told me, "Okay, now reach over here to number 18, which is the neon light outside the window.  And while the scene is going, I want you to
46:12
gently fade it up and down, up and down. Because  that's the neon light out in the alley because
46:20
it's a cheap hotel. There's a neon light out there  saying, "Vacancy, vacancy, vacancy." And there I
46:26
am, you know, 13-year-old Sam, like trying to  do this as evenly as possible. And Bob Briggs
46:31
is yelling at me, "Sam, has any sign blinked that  way ever in the history of blinking signs?" And
46:37
I was like, "No, no, you're right. better. So  there I was like manually figuring out how to blink this thing nicely. That really stuck with  me as a future designer. Um the cue that I want
46:49
to turn that thing up and down. How do I have  that cue only affect the sign and not anything else
46:56
regardless of what other cues have run or not run?  Because as we work through the scene, you know,
47:01
there was a dramatic moment. I had to set up  another cue, crossfade to the other cue, and then reach back over on the other side and  keep blinking the sign. But while we cross faded,
47:10
I had to stop because I needed my hands over here.  In QLab, I could have a light cue that brings the
47:16
neon light up to full, then another light cue  that brings it down to zero. And those light cues could keep running in a little group in a  loop by themselves while other stuff went on,
47:31
right? Here I could have a light cue that is  a very long slow fade of some of my fixtures.
47:44
While here at any time at any time I could  take another cue that brings up another light
47:50
that has nothing to do with the long fade. You  certainly can do that on a tracking console,
47:57
right? You absolutely can do that on other  consoles. For me, for this brain, I can't
48:03
find any lighting console where the it's easier to  look at the two cues and figure out what does what
48:11
and what won't affect what for me for this guy.  So, I find it super valuable this this approach.
48:22
That's the end of that little demo. Are folks with me so far? Does this work for  folks? Are folks already using QLab lighting? One
48:34
is, have you found the sparse cues to be to your  advantage at any time? Uh, no. There's a person
48:40
behind you who is using light. The fact that  cues are sparse and don't collate by default. Oh,
48:47
is that valuable to you? It is. That's you've  been able to make use of it. Yeah. Great.
48:57
Right. All right, folks. We're going to start in  scene three, please. Or actually, we're going to start halfway through scene three. Exactly. Right.  Yeah. Is that um like a in menu-able thing where I
49:08
can go with like a box and then I don't have to  select collate every time. Yeah. So, we haven't talked about this yet, but now is as good a time  as any to. I'm going to go to workspace settings
Cue templates
49:19
and I'm going to go to templates. In workspace  settings templates is a list of every type of
49:26
cue in QLab. And when you select any type of cue  from that list, you get an inspector which shows
49:35
all the inspector tabs that that type of cue has.  You can go to any control and set it to any value.
49:46
And now all new cues in this workspace will  have that value set for that control. You
49:55
could make every light start off being  lavender if you wanted. Every light cue,
50:00
not every light. Or you could do that  too. I guess you could have audio cues
50:06
start off with a specific name or  with a specific number of objects.
50:13
You could have fade cues start with a particular  curve. If you are not an S-curve enjoyer, when
50:21
I work with that lighting designer, that sound  designer who I've been assisting for decades, I
50:27
do this that we have determined over the years is  her preferred fade curve shape. That's what sounds
50:36
nicest to her. So, I do that in my template.  And now all new fade cues have that shape.
50:46
Super valuable, right? What's important to  understand is that's per workspace. So when
50:52
you make a new workspace, these settings won't  necessarily go with I will show you a little
50:57
later how to make workspace templates. [Music]  So you could easily go to light levels collate
51:08
and make that the default. We do not make that  the default default because we would like folks
51:16
to learn about not collating. And if you create a  little tiny bit of resistance, you can often spur
51:23
a little bit of education. And then some people  will resent you for the rest of their lives.
Light language - home and all
51:31
There are a few special commands that I want to point out. One is home and  one is all. When you type all,
51:45
you address every light in your  patch. If you type all red,
51:51
you address the red parameter of every  light in your patch, which has a red parameter. And every light in your patch that  doesn't have a red parameter gets ignored.
52:02
When you type home, all at home means set every  parameter of every light to its home value. The
52:11
home value is an attribute of the light instrument  and it's defined by us when we build like light
52:18
instrument definitions. So for instance um  mo most reasonable lighting manufacturers
52:26
in their manual show you what the home value  of each parameter ought to be. Right? Like
52:33
um many lights that have a strobe channel the  the home parameter is at full. Strobe at full
52:39
means don't strobe let light come through.  Um, most fixtures intensity home value is zero
52:48
because you want to start off with everything  off. Um, most pan and tilt fixtures want their
52:55
home value to be 50% of the way through both the  pan and tilt travel. So when you say all at home,
53:04
you're saying put every fixtures parameters all  back to where their home values are. Yeah. Yeah.
53:10
Can you change the home value? You can change  the home value um on a um type bas like on a
53:19
what am I trying to say? Not by individual  fixture but by individual fixture type.
53:27
Now, if you have two lights that are the same type  and you want them to have different home values, you could duplicate the fixture type and say my  fixture, my fixture special, and they would be
53:39
identical in every way except the special one  would have different home values. So, for example, for your um exercise in your demonstration, you  kept losing the colors. You could make the home
53:50
have color in it. I could What's What's really  going on? The reason that demo went like that is because I did not notice that when I wrote that  demo in for this theater, these lights were in
54:01
a different um personality. Okay? And they were  in a different mode at that time. Since then,
54:08
Alec has discovered it's preferable to use the  mode that they're in right now for assorted reasons. Time wall clock trigger 9:47 a.m. This  is Yeah. Um, since then, Alec discovered that
54:24
it's preferable to have them in this other  mode and I forgot to update the demo. So,
54:29
as it happens in that demo, it wasn't that I  was losing color because I was setting it to home. It's that I was losing color because  I was setting it to a specific value that's
54:39
pertinent to the other version of these lights  personality. But yes, you're absolutely right.
54:47
And for folks with manufacturers haven't all  agreed on what the right thing to do is when
54:54
you home a color changing fixture, right? Like  these color changing fixtures are red, green, blue,
55:03
amber, lime, cyan, and indigo. Is home all  of those colors at full? No. That's not the
55:12
right white. If I do this, every color emitter at  full, to my eye, that's slightly greener than it
55:21
ought to be. But different people have different  opinions. Okay. Well, if it's just red, green,
55:27
and blue at full, I don't know. That's a little  redder than it ought to be. So somewhere is like a correctly calibrated home color. And I think  that it's okay for everyone to feel a little
55:40
differently about that. Maybe. Maybe. I don't  know. That's actually not quite right either.
55:53
So, all at home takes everything out. And then  I have a hotkey here which runs which is not
55:59
working. There we go. I have a hotkey which  brings up that first cue that we've been using
56:05
this whole time to me. to my eye like that  seems like a good color for this skin tone,
56:11
you know, for this particular pasty individual.  Um although this is a fun moment to know that
56:22
actually everyone's skin is the same color because  everyone's blood is the same color and the color
56:29
of our skin is the color of our blood. It is  the tone of that color that melanin adjusts.
56:36
And that's why when you're doing color grading  for video, you'll see a scope with a diagonal
56:42
line. And that diagonal line is right on the  line that the color of oxygenated blood is.
56:48
So when you adjust the color of of film or  video, not film, you you do it with video,
56:55
you adjust it to blood color. And then from there  you tweak based on whether people are sunburnt,
57:02
whether people with um you know with of different  ethnicities have different uh different variation,
57:08
but it all starts from from the blood color. And  there is um something I think that we can all
57:15
learn from the fact that all of our blood is the  same color. Just everyone take it a little easier
57:21
um please. And by everyone I mean certain grumpy  people. Um, okay. Color home. That's where I was.
57:35
Home. So all at home means everything to its  home value. But you can also say certain lights
57:41
at home or certain ranges of lights at home.  Blah blah blah. But home is a special word. Um,
The Light Patch - naming, selecting an instrument definition, addressing
57:51
we started talking about the light  patch and I want to go into greater
57:57
detail because that's where this programming  of lights sort of meets real lights. So,
58:08
I'm going to go into workspace settings and look at light. And we have three tabs. light  patch, light definitions, and light dashboard
58:19
MIDI. We're get to each of those one at a one at  a time. You don't happen to have a pilot with you.
58:27
Okay, great. No problem. I should have mentioned  it before if I wanted it, but I only We'll see.
58:36
These three tabs in um in workspace settings  define how this workspace interacts with lights.
58:43
There's also a window under the window menu  called the light library. And the light library
58:51
is a list of all of the lighting instrument  definitions that are available to QLab at all.
58:58
The majority of these will be sh are shipped  with QLab and we ship about 18900 definitions.
59:06
Um maybe I I haven't updated that number  in my memory, but I have made many lighting
59:12
definitions. So we're somewhere around 18 or  1900. Um and that's not 18 or 1900 different
59:18
types of lights because some lights have a  zillion different versions of their definitions, right? These are uh etc color source 2  luster. Luster twos, right? So luster
59:29
twos can be set to like 12 different modes  that all behave slightly differently. So,
59:38
Luster 2. Yeah, here we go. Luster series 2.  We have direct 10 channel, direct 9 channel,
59:46
HSI, HSI plus 7, HSIC, blah blah blah blah blah  blah blah. So, these are all the different modes
59:53
that the fixtures can be set to. You have to tell  the fixture on the back panel of the fixture what
59:59
mode you want it to be in. And then you have to  use the corresponding definition in QLab when you
1:00:06
tell it to speak with that light. And that's done  in the light patch. And here's how it works. The
1:00:14
light patch is a table. Uh the leftmost column  is the name of the light. Um this is what most
1:00:24
light consoles will refer to as channel. And while  indeed most light cue most lighting consoles will
1:00:32
expect channel to be an integer, QLab goes its own  way. And the name of a light can be any text. So,
1:00:41
we can have it be 11, we can have it  be 100, or we can have it be, you know,
1:00:52
Fred.
1:00:58
Um, crucially, it's easy to do ranges of lights  in a command line when you have numbers. So,
1:01:04
I can say like 11 through 15. Everyone understands what 11 through 15 means. It means  11 12 13 14 and 15. Now I can type
1:01:18
Fred through Susie and all of my lights which are  alpha numerically named right alphabetically named
1:01:24
that fall alphabetically between Fred and Susie  will be included in this range. But it is not as
1:01:31
instinctively easy for people to understand that.  Right? We've all, even I, with my rudimentary,
1:01:37
limited, stunted math skills, even I have an  easier time understanding ranges of numbers
1:01:43
than ranges of text. But what is so often true in  a in a boring conventional lighting plot, you have
1:01:53
front light, top light, side light, whatever. But  you often have a special, this telephone special,
1:01:59
the door special, the window special. And what's  common is for designers to give those specials a
1:02:07
numbered channel like anything else. Okay, so my  front light is all 1 through 10. My top light is all 11 through 20. My side light is all 21 through  30. My back light is all 31 through 40. And then
1:02:19
my specials are 100, 101, 102, 103. And then you  have a magic sheet, a document that you keep on
1:02:25
your desk. 101 is telephone, 102 is door, 103  is window. In QLab, just name the light telephone
1:02:35
because you don't have to do ranges often with the  specials, right? The whole point of a special is it's individually addressed. So you can just type  in the command line telephone at full or probably
1:02:51
phone which is much faster to type. If you want  to number your cue I'm sorry about that. If you want
1:02:57
to number your cues, number your cues. I mean your  your lights. But you could number some and name
1:03:02
some or you could number them all or name them  all. Whatever makes you happy. definition is the
1:03:11
instrument definition that is in use for that  light. So, we just looked at the light library
1:03:18
and you choose the appropriate definition and  that's based on the light that you're actually controlling. The next column is address is you  type here the starting address, the DMX address of
1:03:32
the lighting fixture and QLab fills in a number of  addresses based on the definition. DMX addressing
1:03:40
is um sort of beyond the scope of this class,  but in short, the address of a fixture or of any
1:03:47
lighting controllable device is set on the device.  You tell that light you you are going to be DMX10.
1:03:54
And then it says to itself, well, I need to be  if you if I'm in 10 channel mode and my address
1:04:02
is 10, then I need addresses 10 through 19, which  means that your next fixture has to be addressed
1:04:09
above 19 or else there is a conflict. So you tell  your address your fixtures what their addresses
1:04:14
are. And then here you tell QLab what your fixtures  addresses are. The address necessarily must be
1:04:23
512 or lower because one universe of DMX is  only only goes up to 512. It's 1 through 512.
1:04:34
The next column, the output column is um how QLab knows how to get the message from  QLab to the light. Are you connecting this light
1:04:48
to an Art-net node? Are you connecting this light  to a USB DMX interface? If you have multiple ways
1:04:55
that your uh QLab computer connects to lights,  QLab needs to be told which of those ways you're
1:05:02
using for this individual light. So, uh,  down here in the sort of mini inspector,
1:05:11
when a light is selected, you can set the  name, you can add a note, you choose the
1:05:16
definition from the list of definitions, and then  Chris, do you see I clicked away from that menu
1:05:27
without choosing an item and the whole tab became  deselected? That would typically mean is exception
1:05:39
except it seems that I can  command click on any usually
1:05:44
when there's a very strange UI. So  we'll have okay I have a feeling
1:05:56
this one. Yeah, I mean this workspace has been  around for years. Yeah. Great. Okay, great. So,
1:06:05
some of the weird stuff you're seeing happen  here is me discovering obscure bugs because we're exercising every single piece of QLab.  Some of what you're seeing happen here, though,
1:06:12
might be because this exact workspace was built  for the first ever QLab 5 QClass. And even then,
1:06:20
I copied and pasted in some material from  the QLab 4 QClass. And that QLab 4 QClass
1:06:27
had some copied and pasted information from  the first ever QClass, which I did in 2012
1:06:36
on QLab 3. So there's some history here that  is perhaps giving us a false impression. I'm
1:06:46
sorry that you said what? That is surprising.  That is surprising. Yeah. Okay. That's where I
1:06:51
choose the definition. But now I choose output. Am  I going to speak to this light using Art-net, USB,
1:06:57
or not at all to disable the light, which I might  want to temporarily do. If I choose USB, QLab will
1:07:06
ask the Mac, hey, you got any USB devices plugged  into you that speak DMX? And if the answer is yes,
1:07:11
they will be listed here. If I have multiple USB  devices, they will be listed individually. If
1:07:17
they have the same manufacturer name, you'll also  see their serial number. It's the best we can do, right? If you've got two Enttech USB DMX Mark  1's, you'll see Enttech USB DMX Mark 1 some serial
1:07:30
number USB DMX Mark 1 some other serial number so  you can tell them apart. But if you choose Art-net,
1:07:40
QLab doesn't need to know about the device  or devices because it's just sending Art-net
1:07:45
data out into the network and saying surely  someone out there cares about this information.
1:07:52
And the answer is someone does. And here's how it works. The Art-net node itself  gets programmed to listen for Art-net messages
1:08:07
belonging to a specific net, subnet, and universe.  So we have in this building several Art-net nodes.
1:08:18
Let's say that one of them is a four universe  node. The uh DMX King EDMX4 I think we have or
1:08:29
DMX4 Max. It doesn't matter. It takes network in.  It's got four DMX output sockets. You using the
1:08:36
control software built into the device. You log  into the device and say socket one, I want you to
1:08:42
listen to DMX uh to net0 subnet zero universe  one. Socket number two, I want you to listen
1:08:48
to net zero, subnet zero, universe two. Socket  three, I want you to listen to net 7, subnet 4,
1:08:54
universe 9 or whatever. And then the network  traffic comes in and just like we were um just
1:09:03
like the little barge is sitting there waiting  for barge messages sent to device ID 7, the DMX
1:09:10
node is sitting there waiting for DMX information  coming along in the ARNET traffic that is for the
1:09:18
net subnet and universe that it's hoping for. Oh,  yay. A packet for me. What do I do? I tell channel
1:09:24
7 to go to full. Yeah, there was a question  over here. It's gone. Question over there. Oh,
1:09:29
yes. Um, well, I I had a couple questions, but  I think maybe it's probably easier to ask you at
1:09:36
the end because it's it feels narrow. It Yeah, it  feels like it's not helpful for everybody. Okay,
1:09:41
great. The Art-net spec contains a thing called the  discovery packet. And what the discovery packet is
1:09:49
is um any device that is a lighting controller is  supposed to spit out a packet every two seconds
1:09:57
that says hey I am going to send Art-net data who  out there is interested and a well- behaved Art-net
1:10:06
node is supposed to hear the packet and respond  I am here these are the addresses that or these
1:10:13
are the universes that I'm listening for and  this is my name and these are some information about me. The disco supporting the discovery  packet is optional in the Art-net spec. So,
1:10:23
not every node does this, but if you have Art-net  nodes that do support the discovery packet and
1:10:29
you go to the window menu to the workspace status  window, which we've already been to several times,
1:10:35
to the Art-net tab, you will see all of the Art-net  devices which support discovery packet listed
1:10:43
here with whatever information they say about  themselves here. So, indeed, we have a lobby node.
1:10:50
It's named lobby node because Alec configured  it to say that about its name. This is its IP
1:10:55
address. It listens on this net on this subnet.  And these are the universes that its four ports
1:11:01
are configured to send out. Universe 1, universe  0, universe 1, universe one. Then the DN arch node
1:11:09
is 2322. Then the DN 5 through8 is O. And the DN 1  through 4 is O. What that means is that there are
1:11:16
a total of nine physical ports in this building  that the traffic for DMX universe zero will come
1:11:25
out. So when I patch a lighting fixture to net  zero, subnet zero, universe zero, address 10,
1:11:35
1 2 3 4 5 6 7 8 nine sockets, will if we could  magically put our little magic ear to those
1:11:44
sockets and hear the DMX channels coming out. When  we brought this fixture to full, we'd hear on all
1:11:51
of those sockets, channel 10 at full, channel 10  at full, right? Or less magically, if we plugged
1:11:57
a DMX tester in, we'd see it on the DMX tester.  It's not quite as magical. Whatever. You with
1:12:04
me? That's part of why Art-net is so cool because I  can put nodes wherever the Ethernet network in the
1:12:11
building reaches and then I can tell those nodes,  you listen to this and you listen to that and you listen to the other. You can do the same thing  with streaming ACN. Everything that's good about
1:12:19
Art-net is good about streaming ACN as well with  the exception of how easy it is to write software
1:12:24
for it. Art-net is easier to write software for.  Streaming ACN is not as easy. Then other things
1:12:32
about streaming ACN are better and other things  about Art-net are not as good. But that's neither here nor there right now. This is why I'm trying  my point here is to advocate for Art-net instead
1:12:42
of USB DMX, not to try to advocate for Art-net  instead of streaming ACM. Yeah. Okay, great.
1:12:51
I forget how the net and subnet works.  Is it? Yeah. Okay. There are 100 There
1:12:59
are 128 nets. Each net contains  16 subnets. Each subnet contains
1:13:10
16 universes. That's the categorization of  Art-net. Why oh why oh why did the folks who
1:13:19
invent Art-net need feel the need to include  net and subnet instead of just allowing some
1:13:25
number of universes 0 through 35,000 or  whatever it is. I do not know. I'm sorry.
1:13:32
Sorry. I was just trying to actually  number. Oh yeah, it's a 128 * 16 * 16
1:13:42
32,700 32,700 universes of DMX 512 times 512  should be 16 and a half million million DMX.
1:13:53
So I think it would be much more reasonable if  the Art-net spec just said universe is a number that can go up to 35,000 and there's no such  thing as net and subnet. And the reason that
1:14:01
I find that so frustrating is because  if you go to system settings network,
1:14:07
it's up here now. Thanks, Apple. And you  look at Ethernet, there's a thing called
1:14:12
subnet mask. This subnet and this subnet have  nothing to do with each other and don't mean
1:14:20
anything similar whatsoever, but they both  involve an Ethernet network. Great work,
1:14:26
folks. Keep it up. Maybe I can get you a  job with the USB consortium naming things.
1:14:37
I think the actual reason is that um making  universe go up to 35,000 would require diff
1:14:44
a different number of bytes in programming  rather than having three visually separate
1:14:49
things that have the same number of  bytes. Blah blah blah. I don't care. Point is your net subnet and universe in QLab  have to match the net subnet and universe on
1:15:03
your Art-net node. And your address has to match  the address on the fixture whether it be a light,
1:15:12
a dimmer, a fan, a laser, a barge or whatever.  Yeah, there are some fixtures out there that
1:15:23
support that require more than 512 channels. Some  truly whackadoo fixtures. Those whackadoo fixtures
1:15:32
usually take Art-net straight to the fixture. So  you can just imagine in that case that what's
1:15:38
going on is there's an Art-net node built into  the fixture because that basically is true.
1:15:44
I believe it's possible that there are some  fixtures that receive two DMX cables, one for
1:15:50
one universe and one for another universe just  for the fixture, but I'm not certain about that, so don't quote me on it. There's one picture that  I know that receives a DMX cable and an cable.
1:16:02
Yeah. Right. DMX for the like DMX for the blinder  thingy and for the pixel. Oh, it's 5,000 addresses
1:16:11
per picture. Yeah. the JDC2 by GLP. Yeah. Uh,  of course it's GLP. There's really only two
1:16:18
manufacturers out there, three who do like insane  things like that and it's Robe, GLP, and PRG are
1:16:24
the really insane folks. It is a moving  light blinder pixel-mapped video display, right? Like
1:16:32
you can legitimately watch a TV show on it and  then blind yourself. Yeah. Yeah. that. For those
1:16:40
who don't know, blinder is a lighting slang for  a fixture that's meant to point at the audience.
1:16:47
It's called a blinder because when it goes on  to full, you're like a um and uh so yeah, any
1:16:53
picture that's designed to point at the audience  is referred to as a blinder. So it's right, it's a pixel map, right? I think what would be  much more reasonable is to just have an HDMI input
1:17:01
on it. Um whatever. Okay, the next column groups.  Lights in QLab can belong to one or more light
1:17:15
groups. A light group behaves like an individual  light, but all the commands you give to the group
1:17:24
are given to all the lights in that group. So here  I have an imaginary color source psych fixture
1:17:31
that belongs to two groups called group psych  and group lights. If I say group psych at full,
1:17:38
this light will light up. If I say group lights  at full, this group this light will light up.
1:17:47
These fixtures belong to the group  Voxel. These fixtures belong to the group sides. These fixtures  don't belong to any group.
1:17:57
Note is just a note. It's just for you. So I  could say this light gets front light stage right note. A place to keep information about  the light. We have some tools here for making
1:18:10
um it easy to make and patch lights. And I want  to go through them real quick. To make a new lighting instrument, you either click this button  or click type command N while this view is active.
1:18:20
and you get this little pop-up menu that lets  you create one or several lights at a time. So,
1:18:27
if you're patching your lights and you say, "Oh,  yeah. I'm going to add all of my backlight right
1:18:32
now." And I know I've taken uh I've got I've  hung 12 fixtures for my backlight. And then
1:18:40
see here that command D is next to definition.  You can type command D to pop up this popup. So,
1:18:46
you can keep your hands on the keyboard. Okay.  All my backlight is um color source par. Yeah. So
1:18:58
I typed tab and using the arrow keys. Now I want  to do I want to give them numbers? Yeah. I'm going
1:19:07
to call them backlight 1 through 12. So I'm going  to start at one, increment by one, and prefix them
1:19:15
backlight. And so now you can see down below in  preview my lights will be called backlight one, backlight two, backlight three. Or I could  forgo that and just say they're going to be,
1:19:25
you know, 501 through 503. Or I could go by  twos or tens if I wanted to number them in
1:19:32
some clever numbering scheme. When I  create those instruments, QLab creates
1:19:39
those instruments. Poof. And here they are. and  they start off selected and with the override
1:19:46
uh s symbol because they are not patched. They  neither have addresses nor outputs. I could
1:19:55
manually adjust all of them or I can go to this  button auto patch selected. I'm going to have
1:20:03
them all use Art-net. I'm going to put them all  in universe 6 maybe because that's how I set up my system in subnet zero and net zero starting  at address one. Go. And now we have address 1
1:20:15
through 6, address 7 through 12, 13 through  18 and onward all in DMX universe 6. Yeah.
1:20:26
If you want to make a new group, you can either  click this button or type command G and name it
1:20:33
as you like. Create one new light group. And you  can either just create the group or if you have selected lights, you want to put those lights in  that selected in that new group. It's kind of like
1:20:43
selecting cues before typing uh before hitting the  button to create a new group in the cue list. Yeah.
1:20:51
Okay. By the way, you just found Ethan has fixed  it. Dude is fast. Okay. Are there questions about
1:21:03
the light patch, please? Yeah. As uh progresses  and as technology progresses and stuff like that,
1:21:10
um lighting libraries don't always get updated.  What would be the best way to import an external profile into There is no mechanism for  importing a lighting profile. Um there
1:21:22
has been a very sort of comedically slow paced  movement to consolidate around a single fixture
1:21:32
definition type and GTDF has done an impressive  job of making inroads. It is not universal. And
1:21:40
the publicly accessible GTDF library contains  a total smattering of fixture profiles made
1:21:49
by the fixture manufacturers and made by some  dude on Reddit without any way to tell which
1:21:55
is which. So if you search for a certain light  in the GTDF library and you see two entries,
1:22:01
how do you know which one's the right one?  You do not. There's no label. There's no way to tell. So GTDF is not yet ready  for prime time in this guy's opinion.
1:22:11
Even though it's supported by Vectorworks,  Martin, Vari*lite, ETC, High End. You figure,
1:22:18
all right, those folks are all on board. It  probably should be working. It is not working, reader. So I'm not sure about GTDF. Then there  was the sunlight format. That seemed cool. Kind
1:22:32
of dead in the water. Okay. Turns out a lot of  lighting console manufacturers view their library
1:22:40
as a kind of competitive advantage. Right? When  you buy an ETC lighting console, there's going to
1:22:46
be a definition for your light. I don't know what  light it is, but there's going to be one. And you know what? They're right. I think that's a good  reason to buy an ETC lighting console. I think
1:22:55
it's one of a long list of good reasons to buy  an EDC lighting console, but it's one of them.
1:23:02
So, we can't really reverse engineer ETC's. All  right, that's not going to work. Well, let's look
1:23:08
at lighting manufacturers websites and see what  do they offer as a downloadable fixture format.
1:23:14
And it turns out a lot of closed proprietary  source, closed source or proprietary formats,
1:23:19
which we can't necessarily easily implement  in QLab. So, there's nothing to import. Well, that's a bummer. What you can do is one of two  things. One is make your own lighting definition
1:23:29
for your fixture. It's not that slow to do. Um,  unless your fixture has gazillions of channels
1:23:35
in which case it is time-consuming or send us the  manual and we will make one for you. Um, basically
1:23:44
our policy is anyone who sends us a manual that  we can reasonably make head or tail out of, we will make you lighting definitions and send them  back to you and you can install them real quick.
1:23:53
Then periodically as we release QLab, we take  those and add them to the publicly in to the
1:24:00
the official included library. Um there are a  few that we don't include. Um and sort of I I
1:24:08
edit that list. And basically my sniff test is is  this a real light? Like is this made by grown-ups
1:24:15
for grown-ups to use in real theaters or is this  like some nonsense? And some people are using some
1:24:23
nonsense fixtures. And I have got nothing against  that. I have used nonsense fixtures. I love it.
1:24:28
But I don't want to promote using nonsense  fixtures all the time in regular scenarios.
1:24:35
I'd like to promote using well-made fixtures that  are going to reliably not burst into flames or do
1:24:42
bizarre optical things or scorch your curtains.  You know, like I just So I'm a little conservative
1:24:48
about adding fixtures to the official library. Um,  but we will make you a definition for anything,
1:24:55
no matter how weird it is, as long as you can send  us a document that says which parameter is what
1:25:01
and what does it do? Yeah. Um, could you possibly  describe an upper limit on that nonsense? Because
1:25:11
I have one such unbelievably stupid fixture that  I would love to be able to experiment with with
1:25:18
my computer in my shop instead of dragging it  into the theater. And it requires 481 channels
1:25:25
of DMX. Yeah, this is a job for Lucky Dave, one of  my colleagues. Um, he made uh he made the longest
1:25:34
AppleScript in history which makes it a little  easier for us to make light definitions using
1:25:40
a spreadsheet. So, go ahead and send it in.  I'll show you later. Yeah, it's it's stupid.
1:25:47
It's a dumb thing that I have that I have. I  don't know how we even have it. Awesome. Yeah,
1:25:53
send it in. We'll make it for you. We'll do it.  Great. Um um but you can also make your own. You
1:26:00
make your own in the light definitions tab or  in the light library. I'm going to bring both
1:26:07
these windows up at once because they are related  but different. The light definitions tab in the
1:26:16
workspace settings window lists all the lighting  definitions that are included in the workspace.
1:26:24
Whenever you add a light to your patch in QLab,  the definition that you use for that light gets
1:26:30
copied into the workspace. So every light that has  ever been part of your workspace, its definition
1:26:38
is copied into and stored inside the workspace.  The reason for that is what happens if you take
1:26:45
your show and bring it to another computer and  that computer is running an older version of QLab
1:26:52
that doesn't have the light definition that this  one has or what if you made a custom definition.
Making and editing light instrument definitions
1:26:58
We don't want to rely on a monolithic library.  We want every workspace to have its own copy
1:27:03
of lights. What if you customized it uh to have  its own home values, its own special home values
1:27:09
as we discussed earlier. So every light that's  patched in QLab in a QLab workspace that definition
1:27:15
gets copied into the light definition into the  workspace and is visible in the light definitions tab. You can create a new light definition here  that belongs just to this workspace or you can
1:27:26
create a new definition here that is available  to all workspaces on this computer. You with
1:27:34
me? So for your whackadoo light, if you just  want to have one little project and you don't
1:27:41
want to ever use it again or you don't think you  don't want to ever use it again by accident, you
1:27:48
could create a new workspace, create a new light  definition in that workspace and get to town.
1:27:57
Whackadoo made by I don't  know, American DJ probably.
1:28:04
Then we add parameters. Oh, it's got  400 parameters. Oh, well, let's go, you know, three at a time. What's the  first one? Pan. Uh, what's the next
1:28:12
one? Tilt. Great. Are the parameters 16 bit? I.e. do they use two DMX channels together  or do they use only one? If it's 16 bit,
1:28:23
you see that the next one automatically bumps  to three. Should I use a percentage value when
1:28:29
displaying the value to the human or should I  use a raw DMX value when displaying to the human?
1:28:39
It doesn't actually change how it behaves. It just  changes what's visible. The only reason you'd use
1:28:45
one or the other in my opinion is if um like when  you use a gobo rotator built into a moving light,
1:28:53
the manual will show you a list of DMX values  that correspond with certain positions or a
1:28:58
gobo selector. Right? I've got eight goos on a  little wheel. DMX 72 is the stars gobo. That's
1:29:05
when it's useful to not use a percentage value.  So you can look up the value in a manual or um a
1:29:12
lot some lights that have adjustable frequency for  matching um when you're using them on camera will
1:29:19
say oh yeah it's just um 255 DMX 255 is 25.5  hertz and DMX you know 186 is 18.6 hertz or
1:29:31
whatever or 186 hertz or I don't know what it is.  Point is, sometimes it's useful, other times it's
1:29:38
pref preferable to use a percentage value. Next,  you set the home value, right? So, you can set
1:29:43
home to full here, home to 50. For pan, I would  set home to 50. For tilt, I would set home to 50.
1:29:53
GH exception. This is this is probably one of those  things where it's not QLab's fault,
1:30:01
it's Sam's fault for having an ancient workspace,  but also there is a little exception in the light
1:30:06
definition editor sometimes. And we've just found  it, I think. Okay. Force quit. First of the first
1:30:14
of the class. What? Made it three days. Made  it three days. What? 15 hours. Yeah. Especially
1:30:22
when what I'm doing is specifically torture  testing QLab. I'm pretty pleased with that.
1:30:34
Now Chris. Oh, okay. It just took time.  It just waited for me to say now Chris.
1:30:50
Oh, yeah. It didn't save because I hadn't say,  you know, I hadn't saved right before we had the crash. So, we made the new light. We named it.  We named it. blah blah blah. You can set your
1:30:57
default parameter here. So that's how you make  your own definition. Virtual parameters are worth
1:31:04
discussing. Um let's look at this Maverick force  2. These are the parameters that are defined by
1:31:15
the manufacturer. Pan tilt, pan, tilt speed,  intensity, shutter, blah blah blah blah blah. We have some house style on naming parameters  uh all lowercase. Um um if we have a multi-ell
1:31:30
instrument, right? So it's like a strip light  that's got six cells in it. I say red for each
1:31:36
cell is red space one, red space 2, red space 3,  red space 4, blue space one, blue space 2. That's
1:31:41
just house style. It's not important though. If  you want to use your own methodology, use your own methodology. Another house style is um gobo gobo  channels. Everyone describes them differently.
1:31:53
gobo fixed, gobo static, gobo rotating, gobo  non-rotating, whatever. We always say gobo one,
1:32:00
gobo two, gobo 3. Also, gobo one rotation is  always the rotation channel. Sometimes it's
1:32:06
called different things on different fixtures.  We always call the in the channel that means the
1:32:11
brightness intensity. Unless the fixture has both  an intensity channel and a literal dimmer channel,
1:32:19
which some fixtures do, then we'll  we'll call them intensity and dimmer.
1:32:26
Anyway, that's just house style though. So,  if the idea is that fixture library that we
1:32:31
make should feel kind of consistent. If you make  your own fixture, call things whatever you want to
1:32:36
call them. We don't care. But virtual parameters,  virtual parameters are the way that QLab produces
Instrument definitions - virtual parameters
1:32:48
this interface here because the Maverick has  cyan, magenta, and yellow channels. But in order
1:32:57
to have a CMY color picker, we have to tell QLab,  hey, those cyan, magenta, and yellow channels,
1:33:05
they belong as a batch in a CMY color virtual  parameter. So this PIP here lets me remote
1:33:15
control the cyan, magenta, and yellow parameters  of the fixture using a Groovy graphical interface.
1:33:22
But the actual data that gets sent to the fixture  is individual channels cyan, magenta, and yellow.
1:33:29
We also have a virtual pan tilt parameter which  lets us use this groovy pan and tilt interface
1:33:35
to control the pan and tilt parameters. The  types of virtual parameters we have are RGB
1:33:42
color parameters which also include RGB plus other  emitters like cyan, uh, amber, magenta, lime, etc.
1:33:52
CMY is this HSI color pickers let you choose hue,  saturation, and intensity. The pan tilt parameter,
1:33:58
which you see here, and what we call a one to  many parameter. If you want to have one parameter that remote controls several, for instance, if you  have a multi-ell strip light, it's got six cells.
1:34:10
Each cell has its own red, its own green, its own  blue, and its own intensity, but the manufacturer
1:34:17
has not given you a main intensity control. It  can be annoying to type intensity.1 intensity.2
1:34:25
intensity three intensity.4 blah blah blah at  full. It would be nice to just say intensity at
1:34:30
full. So you can make a one to many parameter that  gangs together all the intensity parameters and
1:34:35
just call it intensity. And then you can set the  default parameter of that fixture to intensity.
1:34:41
And then you can just say strip light at full go.  And the the virtual parameter distributes that
1:34:48
number to all of its one to many constituents.  Yeah. So those are our virtual parameters.
1:34:59
That is the light definition editor. And so that's  how you can make your own light. And that's also how we will make a light for you. Do not be shy  about sending lights to us. We're happy to make
1:35:08
them. This bit of QLab is, we admit, not super  speedy to use because it has to accommodate a
1:35:16
sort of strange and wide range of possibility. So  send us the things. We will make it for you and
1:35:23
send it to you. And if it's a light that feels  like there's some snowballs chance that other
1:35:29
people are likely to use this thing, too, and we  think that it ought to be so, we will include it
1:35:34
in a future release of QLab. I try to keep up with  the biggies. I try to keep up with ETC, Vari*lite,
1:35:44
Martin, Chauvet Professional, Chauvet DJ, I keep  up with slowly because they make a truly alarming
1:35:52
number of new fixtures every year. It's stunning  how fast they move at Chauvet DJ. But Chauvet
1:35:59
Professional is a little more modest. Although  they release lights in a way that is hard to
1:36:06
understand, right? Like the storm 4 has been  coming soon for quite some time. It may be here
1:36:12
now, but it took like it was more than a year  that it was coming soon and the DMX addresses
1:36:18
were not available on their website. So I was  like, let me add it. I'll type it up. Anyway, doesn't matter. Yeah. Speaking of shop, you  have two iterations. There's a space in one
1:36:28
of them and not in the other. So there's a  sorting issue. where in the general library.
1:36:37
Indeed, we do. That's an error. Just  letting you know, the SlimPAR T12 BT
1:36:43
should have had that space. That's  one for me. Do you mind writing it down,
1:36:50
though? Yeah. Could you get for me that the  SlimPAR T12 BT has a typo in its manufacturer name,
1:36:58
which is a missing space? Thank you for that.  That's a mistake. But can you blame me? Look
1:37:05
how fast they go. I mean, come on. That's a lot  of lights. Also, if it makes you feel any better,
1:37:11
your shop inventory of fixture profiles  might be better than just Yeah, take that.
1:37:22
You hear that, Nick? Nick Gonsman is the... yeah.  No, I'm a big fan of Nick. We're we're very
1:37:28
friendly. I'm not I'm that's completely a joke.  Um ETC's fixture library folks are incredible
1:37:36
and and they also well never mind. They they  are they are really really good at what they
1:37:42
do. That's that is the sum total of my opinion  there. They are really good at what they do and
1:37:48
um I admire them. Um uh some of these are  subtle but interesting, right? IED mapper
1:37:56
was a program that came out for iPhone many  years ago. I don't think it exists anymore, but it made a 4x7 grid of squares on your phone  screen and each square was an RGB light. And so
1:38:08
you could hold up your phone and send Art-net to  it over Wi-Fi and it would do stuff. And in fact,
1:38:16
we did a production of Be More Chill at the  summer camp where I teach. And we had there's
1:38:24
a song in that play called Cell Phone Hour where  all the high schoolers are talking to each other
1:38:29
on the phones. Oh my god, did you hear what  happened to so- and so and did you hear what happened at that party? And and so we put Mapper  on all of the campers cell phones and had a very
1:38:39
elaborate cue playing over their phones, lighting  up the side of their face. Then they would hold up their phone and you know it was really cool.  It worked really really well and all you need
1:38:49
is one excellent Wi-Fi access point that is  not connected to the internet um that all the
1:38:56
phones are connected to. So that's why we have iL  mapper because it's just too cool to not include.
1:39:03
Um any other questions about the light library?  Yeah, it's not about the library, but Oh, yeah.
Art-net and multiple network interfaces
1:39:13
How do you know which network or is it just  going out? Yeah, that's a great question. Um,
1:39:20
so the first answer is the broadcast packet is  supposed to deal with that for you. So, I'm sorry,
1:39:29
the broadcast the discovery packet is supposed  to deal with that for you. QLab is supposed to say like, "Hey, Art-net nodes, are you out there?" And  they say, "Yes, here I am. Here's my IP address.
1:39:37
Oh, if that's your IP address, then I know  what net you're on. If you go to QLab menu,
1:39:43
QLab preferences, hardware tab, down at the bottom,  Art-net lighting network interface. Automatic means
1:39:54
QLab will figure it out. But if you have Art-net  devices that don't respond to the discovery
1:39:59
packet and or are weird and or you have a very  esoteric network setup, you may need to choose
1:40:06
a specific network adapter. Right? So here right  now I've got two active network adapters. I've
1:40:11
got the built-in Ethernet port on this Mac and  then I've also got an Anchor Ethernet adapter
1:40:18
plugged into a USB port. If I know for sure that  the anchor adapter or the built-in Ethernet is
1:40:25
on the physical network that all of my Art-net  stuff is on, I could choose that. And in fact, I do. I know that it's the Ethernet the the five  subnet. I could choose that here. But because all
1:40:37
of the DMX nodes on this network respond to  the discovery packet, then that means that
1:40:49
QLab already knows that they're all on the  five subnet. It means that leaving this at automatic and setting this to five will make  no difference. So it's not outputting to the
1:40:59
other. No, it's not flooding the six network.  Now in fact it's not flooding at all because
1:41:08
um this next check box use broadcast mode for  Art-net lighting that when you check that box it
1:41:17
amplifies dramatically the amount of network  traffic coming out of QLab for lighting because
1:41:22
broadcast mode for Art-net says I don't care what  nodes are out there and I don't care what they can do every IP address on this network is getting  packets from me. If you have nodes that don't
1:41:34
dis support the discovery packet, you may need to  use broadcast mode because QLab can't find out what
1:41:40
IP address is receiving. There's a little more  nuance to it and I'm glossing over some details,
1:41:46
but in short by DMX King or other well- behaved  Art-net nodes and then you won't need to really
1:41:54
worry about this. I mean, there are plenty of  other well-behaved... Doug Fleenor. I forgot to say Doug Fleenor earlier. Nothing they make isn't  great. It's a little clunky looking, but great.
1:42:05
Yeah. Are there any similar third party Ethernet  adapter concerns with Art-net as there are with
1:42:19
there used to be, but since the advent of 2.5 Gbit  and 10 Gbit Ethernet, it turns out that gigabit
1:42:26
Ethernet is now the most common type. you really  don't need to really worry about it. I mean,
1:42:31
maybe truly flaky ones, right? I like Anker. I  like Belkin. The only reason I like Belkin,
1:42:40
though, is because there are a lot of products  that Belkin sells which were obviously designed by Apple. Like, obviously. And Apple doesn't want  to be in the business of selling that stuff. So,
1:42:52
they're like well- behaved Ethernet  adapter Belkin. Why don't you sell that?
1:42:59
Except theirs is one of the bad ones.  One of theirs is one of the bad ones.
1:43:07
Um but like for a while the only truly  good um standalone HDMI USBC dongle was
1:43:16
a Apple design product made by Belkin. It's  not true anymore, but it was true. So, no,
1:43:23
I haven't come across any Ethernet adapters  that I'm sure are no good for Art-net. Um,
1:43:28
but use a well use well-built cable, use a  gigabit network, get on with your life. Keep
1:43:39
Dante and AVB and NDI away. Dante behaves best  without a DHCP server. Dante wants link local
1:43:52
addresses where you just like let every device  say its own address and there's no DHCP server
1:43:58
on the network and no one's set to a static  IP. That's how Dante likes to be. So when I do
1:44:05
um show control, when I do when I do systems  for large shows, I have a Dante primary network,
1:44:12
a Dante secondary network, a control network, and  they are three physically separate networks or
1:44:18
three VLANs on a well-built VLAN capable switch.  Um yeah. Anything else in this area before we move
1:44:31
on to other areas? Yeah. Can you do um when you're  doing addressing for like let's say I have a group
1:44:40
of 10 fixtures. Can you do offsets? No. No. Okay.  It would be nice. It would be nice. Right. So I
1:44:47
have 10 fixtures. They all use six addresses  but I've addressed them as 10 20 30 40. Yeah.
1:44:56
You have to individually address  those fixtures. Yeah. But um yeah, I think it would be cool if I  could address them at like, hey,
1:45:03
address all the selected as 10 + 10 and then  it would go by 10. That would be really nice.
1:45:13
Um broadcast mode automatic. We got there from  this, we got there from that. We got there
1:45:21
from Any questions? Yeah. Other questions about  lighting patch? Okay. If you have made changes
Managing instrument definitions
1:45:30
to a lighting instrument in one or or created a  fixture in one workspace and then you subsequently
1:45:39
decide I'd like to make that val that uh that  instrument definition available to all the new
1:45:48
workspaces on my Mac. You can save to library  and it will save it to the Mac's library. That
1:45:54
library lives on the Mac, not in QLab itself.  So you if you um it it doesn't send it to us,
1:46:03
but it saves it to that max library which  is stored in your home folder in your in
1:46:08
your library folder. If you copy a fixture  from the library by virtue of patching it in
1:46:14
QLab and you make some changes and then you  decide, no, I was wrong. I wish to go back
1:46:19
to the default. You can update from library  and then the version of the light definition
1:46:26
that exists in the workspace will copy will be  replaced with a fresh copy from the library.
1:46:36
Likewise, in the light library, um, no, never mind. Forget forget that. That was  a gonna that sentence was going to say nothing.
1:46:48
You can of course also export.
1:46:53
This export button at the bottom of the settings  window also allows you to export light patch and
1:46:59
import it into another workspace. So if I build  a light patch for the house plot in this theater
1:47:06
in this workspace and then someone comes along  and says, "Hey, I'm doing the next show in there and I'm not rehanging lights. Can you give me your  light patch?" Yeah, I can export the light patch,
1:47:16
send it to you, you import it into your show.  Voila. Yeah. Okay. I have a question about your
1:47:26
question. The for the offset was uh it was  the desire is to if you're starting at let's
1:47:35
say DMX1 to be able to say jump an entire 10  before the next. Yeah. Here. So these these
1:47:41
five fixtures are addressed 211, 218, 225,  232, 239. They're continuous, but you want
1:47:48
to leave gaps between them. Leaving gaps makes it  easier to remember the address of your fixtures
1:47:54
when you're standing on the floor looking at  them. So I have that's 211, that's 221, 231,
1:48:00
241. Great. I'm just writing up an issue for Yeah.  Um there should be an existing issue. Okay. um or
1:48:09
a commentary in an existing issue about speeding  up patching. Um now leaving gaps of course is
1:48:17
effectively wasting addresses. So if you've got  a crowded show, you don't do that. Um, and also
1:48:26
since batch patching like this is so easy, it's  also not that rare to be like all my cyc lights
1:48:32
address one and then I just go sequentially so  that I can use the existing auto patch tool. But
1:48:39
in in another environment it can be really nice.  Yeah. And that also helps for changing profiles.
1:48:47
Like sometimes you want to leave room for the  highest profile and not sure which one you want to use yet and then if you want to downsize, you can  do that easily. Yeah, if you know you have enough
1:48:56
channels to do it that way, right, that could  be really convenient. You're absolutely right.
1:49:04
Um, all right, that's the light patch, the  light definitions. We're going to do the light dashboard MIDI tab and then we're going  to take a break. The light dashboard MIDI tab
Light Dashboard MIDI control
1:49:15
allows you to assign MIDI controls in the physical  world to controls in the light dashboard because
1:49:26
folks like to lay their hands on things to  control lights. Mouse and keyboard is nice,
1:49:33
but look at any lighting console. There's  sliders and wheels and knobs and things, right?
1:49:40
So, when you look at the light dashboard  MIDI tab, you'll see a list of every light in your patch. And you can select an  individual parameter of that light
1:49:49
and either hit the capture button or describe a  MIDI message using this menu and this text field
1:50:00
and QLab will attach incoming MIDI messages  of that sort to that parameter. If you have
1:50:08
a fader surface with motors in it, you can send  MIDI feedback by finding your MIDI device and
1:50:14
telling it what channel you're going to  send MIDI to. So, Alec and I collaborated
1:50:19
on a thing called the pilot, which is a  MIDI fader and encoder surface for QLab.
1:50:27
You can tell a fader to control the  intensity of lights 220 of a light 220.
1:50:36
You could also use a fader to control all  lights intensity if you wanted or just the
1:50:44
selected lights intensity. So here control change  one if I had the fader surface here control change
1:50:52
one says whichever light is selected in the  dashboard control its intensity with this fader.
1:51:04
Your special selectors up here are selected and  then every group light group that's in your show,
1:51:11
then every light that's in your show.  And subcontrollers comes first. We'll talk about subcontrollers later. So, this  gives you a way to assign MIDI messages
1:51:22
to control your fixtures. Um, any MIDI  surface will do. Motorized MIDI surfaces
1:51:28
make the most sense because then when you  make a change on screen, your change is reflected in reality on the control surface,  but non-motorized surfaces do fine as well.
1:51:40
Remember yesterday I said I'll only ever say this  one nice thing about Behringer, which is that they support OSC very robustly. The other nice thing  that I used to say about Behringer was that the
1:51:50
Fader X is the um or no, what is it called? The  X-Touch, whatever it is, they have a little eight
1:51:55
fader controller with a bunch of buttons and a  bunch of knobs. And I for a while I was like,
1:52:02
that's the only motorized MIDI control surface  under $2,000 that's any good at all. Um,
1:52:08
and I'm now comfortable saying it is no longer  the only one. And since I don't like to recommend
1:52:14
Behringer for any reason, because I find them to  be both physically and ethically disgusting, uh,
1:52:21
I encourage you not to buy them. They steal things  from people. They buy products, rip them apart,
1:52:29
copy everything, and they got caught in court once  because they copied a mistake that someone else
1:52:35
had made. The same mistake showed up in their  product identically. Um, that doesn't seem to
1:52:41
stop them. Um, and also, Uli Behringer is a huge  anti-semite, so screw that. Yeah, I was just gonna
1:52:48
say that uh at Ruckers we have Midas M32 boards  and uh they're very similar to the Behringer X32
1:52:56
since Behringer bought Midas. Yeah. Yeah. Because  Midas Midas had backed themselves into a niche
1:53:04
uh that was unsustainable financially for them.  They had really great consoles that were really
1:53:11
only usable in a kind of narrow context. So, they  were ripe for uh taking over. Um, the M32 console,
1:53:20
as I understand it, is slightly better made  than the X32 console. Um, so the physical build
1:53:25
quality, which is the X32's real weak link.  If you just take ethics aside for a moment,
1:53:31
the X32 is affordable, flexible, powerful, but  they've got like a 50% failure rate. And if you're
1:53:39
one of the people whose X32 has never failed you,  then you say, "What? What are you talking about? Things work perfectly for years and years and  years. It's a tank. Um, but if you're one of the
1:53:48
people who's not one of those people, then you've  discovered the other thing, which is it's just like some of them are not very well made and like  you drop it slightly and it's over. So, I would
1:53:58
really rather people buy SQ6s instead of X32s for  their small console. Slightly more expensive, but
1:54:04
it's like triple the reliability and like 10 times  the ethics. And also, it sounds slightly better in
1:54:10
my opinion. Um, that said, the little Behringer  fader thing is not bad. The faders are way noisy,
1:54:20
but it's not bad. And that's what I was using  until I got fed up with it and Alec uh started
1:54:27
building something and then we collaborated a  little bit. So, now I like the one we make. Um, but I also uh found another one who makes it. It's  gone. It's out of my head. It's invisible to me.
1:54:40
Motorized fader surfaces are groovy and you can  use them. Non-motorized fader surfaces. Akai makes some really good cheap non-motorized MIDI  controllers. Uh, a lot of like um inexpensive
1:54:54
um MIDI pianos have a little fader surface built  in which you can use for this. So, there's some good stuff out there. Um, and I recommend it. I  would love to hear about how people are working
1:55:07
with physical controllers and how it's working out  for them and what they would like to do that they
1:55:12
can't or what they would like to do that they  can that they wish work differently for what reason. Um that would be really interesting  information for me. Any questions here?
1:55:27
Okay, let's take a little uh break. you know,  the the little five to 10 minute range. Um,
1:55:35
use the restroom, get a drink  of water, stretch your legs, whatever. And when we come back, we will  wrap it up with lighting and move on. Thanks,
Break
2:06:39
Hello. Here I am. We're back. Uh, and let's talk  about the light dashboard. So, I've started um you
The Light Dashboard - making cues, updating cues, latest cue, originating cues
2:06:49
know, I've already started using this a great  deal, but I want to go through this interface
2:06:54
entirely and in detail because there's a lot  of power in here which is easy to blow past. Um
2:07:04
uh the first thing I want to talk about is sort of  a fundamental premise of lighting in QLab, which is
2:07:10
the idea of changes versus all. In QLab, in the  dashboard, we use the word record and the word
2:07:20
update together with the word changes and the word  all. And record and all go together and update
2:07:28
and changes go together. In short is like this.  When I make some changes in the light dashboard,
2:07:43
those changes are drawn in yellow. The  things I changed are drawn in yellow.
2:07:50
And when I make a new cue from the light  dashboard, I click new cue with changes and I
2:08:00
get a light cue where everything in the levels  tab of that light cue is one of those yellow
2:08:07
parameters. Crucially, none of the parameters  that I didn't touch are recorded into that cue.
2:08:18
But if I go and make some changes
2:08:27
and then I click new cue with all, I get a new cue  that has every single parameter of every single
2:08:36
fixture included. For those of you who are more  intimately familiar with other lighting consoles,
2:08:44
you'll recognize this as a blocking cue. Every  parameter of every fixture in my show has a
2:08:52
value in this cue. And so when I run this cue, it  is a definitive statement of yes, all the lights
2:08:58
should be like this. Now, if I add lights to my  workspace after the fact, those lights will not
2:09:08
get added to this cue. The cue doesn't know  that it has all the lights or not. However, the
2:09:17
first command in a new cue with all uh in the first  command in a light cue which is created with the new
2:09:24
cue with all button is all at home. So in a sense,  even if I add new lights, they will be represented
2:09:34
in this cue. They'll just be represented in this  cue at their home value. So those lights can be
2:09:41
guaranteed to be set to their home values whenever  this cue runs. Making a new cue with all is the way
2:09:48
that you create a dividing line in your workspace.  Also, it's a way to help you clock where collated
2:09:58
cues will stop looking up, right? It's not that  the collated cues won't look past the new cue with
2:10:05
all. It's just that you know for sure that the  new cue with all has commands for everything. So,
2:10:11
the cue the collating cue doesn't need to look  up past the new cue with all. Any cue that
2:10:17
has all with home in it is going to sort of be  definitive. Does that make sense? Okay, great.
2:10:27
If I make some changes in the board in the  board in the dashboard, uh these two cues
2:10:34
these two buttons will also light up record all  and update dot dot dot and they have dot dot dots following an old macOS convention. Anytime  you see an ellipsis in a button or a menu,
2:10:45
what that is supposed to mean on the Mac is  more input is necessary from you before anything
2:10:52
actually happens. That was the original definition  of an ellipsis in a menu item or a button on Mac
2:10:58
OS. So when you say new workspace, QLab makes  a new workspace. Salute. But when you say new
2:11:08
from template, which has an ellipsis, QLab asks you  what template before actually making a new one.
2:11:19
Close closes. Save saves. But save as dot dot  dot requires you to put in the name that you're
2:11:26
saving as. So the dot dot dot means more input  before action. Strictly speaking, view change
2:11:34
log dot dot dot shouldn't have the dot dot dot  because no input is needed from you. I'll take
2:11:43
a but but there's this this is I'm saying strictly  speaking but Apple's guidance on this is ambiguous
2:11:51
because view change log dot dot dot does require  you to close this window before you can proceed.
2:11:58
So in a sense you do have to take another  action before you can go on which is get
2:12:04
rid of the window. So opening a modal counts  as dot dot dot. So it's I'm not blaming us.
2:12:12
I'm blaming Apple for their ambiguity here  in view change log. Check for updates dot
2:12:18
dot dot requires you to say okay to get rid of  the message saying no new updates or requires
2:12:27
you to click the button saying yes do the  update or no don't do the update right now. So that's why there's the dot dot dot. Yeah.  So record all and update dot dot dot. When
2:12:37
you click that button a little tiny menu pops  up. Do you want to update the the latest cue,
2:12:45
the selected cue, or the originating cue? I'm  going to define all those in a moment. Or record all. Do you want to record all to  the latest cue, the selected cue, or to a new cue.
2:12:58
And what update will do is copy the yellow values  into either the latest cue which is listed here.
2:13:07
Talk about that in a sec or the selected cue or cues  if multiple cues are selected or the originating cue
2:13:13
which I'll talk about in a minute. Whereas, [sneeze] salude,  record all either update either changes the latest
2:13:19
cue, selected cue, or makes a new cue with every value.  So record is a overwriting change. If there are
2:13:28
values in the light in the light cue that you have  selected and you choose record all to selected,
2:13:34
those values that currently exist will be erased  because everything that's in the dashboard is
2:13:39
being used to put into that new into that cue.  Does that make sense? Latest cue is a QLab concept
2:13:49
that we've come up with to answer the question  that stage managers and directors often like to
2:13:55
ask the lighting designer. What cue are we  in? Now, in the world of audio, the question
2:14:00
of what cue are we in is a known and understood  nonsense question, right? Because if I'm playing
2:14:07
my weather, what cue are we in? Well, do  you want to know how many different sounds
2:14:13
are playing right now? Do you want to know the  group cue that contains those sounds? What if I'm also still playing the transition music because  it hasn't faded out yet? We're in several cues.
2:14:25
What cue are we after? I can answer. What cue  is next? I can answer. But what cue are we in is
2:14:31
vague and difficult to pin down. Folks who do,  for example, sound for dance find this mystery
2:14:40
mysterious. I know exactly what cue I'm in.  We're in dance seven. I'm playing song seven.
2:14:47
But I encourage you, if this is if  it sounds like I'm speaking nonsense,
2:14:53
I encourage you to think expansively about the  idea that multiple cues can be running at once. So being in a cue means nothing. But lighting  usually on a etc console, on a Grand MA console,
2:15:07
usually you are in one cue because all the  lights that are up are up at the value that
2:15:13
a cue told them to be in. unless an effect is  running which we categorize as separate from
2:15:19
cue's. But since QLab has sparse cues, the look  that's on stage right now could be the result
2:15:25
of several cues if I'm not using collating. If  I ran cue 1 2 3 4 5 and it brought up that light,
2:15:32
that light, that light, that light, that  light, and they don't collate. I mean, I guess I'm in cue 5, but I'm also in cues 1 through  4. So QLab instead says what is the latest light
2:15:43
cue that ran? That's the only thing we can tell you  absolutely for sure. The latest light cue that ran
2:15:50
is vox NUM asterisk Voxel class home which is not the most usefully named  or numbered light cue. I admit it is this light cue.
2:16:02
If I run some other light cue,
2:16:10
that is now the most recent light cue that ran.  Whether or not things changed, that's the most
2:16:15
recently run light. So latest is the most is  the most useful thing we can definitely tell
2:16:23
you that's true about lighting in QLab in terms  of what cue has happened. and record all and update
2:16:31
allow you to update the latest cue. And the idea  of the workflow here is run a light cue. Oh no,
2:16:38
don't like this. Change, change, change, fix,  fix, fix. Now I like it. Update latest. Right.
2:16:50
Selected is not that complicated. Selected  cues are the ones that are selected in the cue list. Yeah. But now I want to talk about  originating cues because they're a little
2:17:01
weirder. When we did this demo with the  sparse cues, and I'm going to try to
2:17:13
Oh dear. Oh no, no, no, no. Watch that, Sam.
2:17:30
I'm trying to run this without  running the light cues.
2:17:40
Okay. Why is two lit up? It's not important.  When we did this demo, the live values of 80,
2:17:48
10, 100, 130, 50 were the result of multiple  cues that ran before the cue that is responsible
2:17:59
for each of those live values is called the  originating cue for that value. So at the moment
2:18:07
in time when the live values are 80, 10, 100, 30, 50; cue 4  is the originating cue for light 11. Cue 3 is the
2:18:18
originating cue for 12. Cue 2 is the originating  cue for 13, and cue 2 is the originating cue for 30
2:18:28
and 50. If I make changes in the dashboard to  lights 11, 12, 13, 14, and 15, and then I choose
2:18:41
update originating cues. I suppose I could I realized  just now as I was saying it,
2:18:50
I could just do it instead of describing it.
2:18:59
If I make changes, which I'm going  to do to the color of these lights.
2:19:20
Oh, no. I'm not because these uh I didn't because  we had a QLab crash. Mhm. So, we have to go to the
2:19:29
light patch and recreate that change that I made.  We're going to get rid of all these suckers.
2:19:39
We're going to renumber you. 11 and update.  12 and update. 13 and update. 14 and update.
2:19:52
15 and update. 16 and update. This is the  most exciting part of the class, right?
2:19:57
What did you do for three days in Baltimore? I  watched a guy type. Uhhuh. Uhhuh. And why? Well,
2:20:05
that's a different story. Okay.  Now that I've hit all these cues,
2:20:12
I'm going to give 11 a color, 12 a color,  13 a color, 14 a color, 15 a color.
2:20:26
Okay, so I've now made changes in the dashboard.  I have all these yellow values. The latest cue is
2:20:35
LX4. That's here. If I update latest,  all those color changes I just made,
2:20:43
they're going to end up in LX4.  But if I update originating,
2:20:49
now each cue...
2:21:06
The cue that originated the color for each of  those lights turns out to have been the reset
2:21:14
cue that was at the beginning of the demo. So  now those colors all get copied backwards up
2:21:20
into that originating cue. If I go here  and in this cue I add a color command.
2:21:35
Now this cue has a color here.  I can add a color command. Now
2:21:42
this cue has a color. So when I run  my way through these cues again,
2:21:52
if I now want to make more color changes,
2:22:00
everybody goes pink and I update originating. I  have three originating cues to update. Why three?
2:22:09
Well, in light cue 2, I added a color here. So  that's the originating cue for 14. In light cue 1,
2:22:20
I have a color for 11. That's the originating  cue for the color of 11. When I do this,
2:22:28
update three originating cues. Light one is  updated with the new color for 11. Light two
2:22:34
is updated with the new color for 14. And the  other three colors are updated back here in
2:22:41
the reset cue. Does that make sense? Update  originating is the way to reach up in the past,
2:22:47
find the place that the thing was set and say  all along you should have been this other value.
2:22:56
Yeah, just to clarify, please. going  backwards. If you have let's say like Q1,
2:23:02
let's say we're talking about one light just  for simplicity, like Q1 sets color, like Q2
2:23:07
sets intensity. If you change like Q3, you make  changes whatever you update backwards, it will
2:23:13
update both because the intensity was in Q2 in  Q1. If I make changes to both color and intensity,
2:23:25
yeah. Yeah, this feels potentially dangerous update  originating. Yeah, like no more so than trace,
2:23:37
right? I suppose not. But is there a certain  like like is there a command Z on that if I
2:23:44
accidentally update originating and now  it's like oh my whole pathway for that different? I actually don't know. Let's  try it. So here in this selected cue,
2:23:53
I'm going to say um we're going to combine demos,  right? 11 through 15 at full. Nope, that's at 10.
2:24:08
Now I'm going to make a new light cue that is
2:24:18
color it this dramatic pink. And while I'm  at it, I'm going to make sure that 11 through
2:24:24
16 are all in my Voxel group. Yeah. So Voxel,  which is a group at color at pink. So let's go.
2:24:39
So first I bring my intensity up,  but I see nothing because no color is set. Now I bring my color up very  very pink. Now I want to say ah you
2:24:51
know what that intensity is wrong.  The intensity should be like this.
2:24:59
If I update originating, that updates this  originating cue. But if I command Z. Yeah. Undo.
2:25:08
I don't want to do that on accident. Oops.  That's the whole channel I changed. Yeah.
2:25:15
So um the idea the idea with update originating in  essence is I'm doing a play lights up on a scene
2:25:27
then a change then a change then a change and then  the director re-blocks the scene and says you know
2:25:33
what Steve you should have when you enter just go  right to the window and sit and stare longingly out the window and now Steve is sitting at  the window out of light because no one was
2:25:42
there before. So, okay, I'll bring up that light.  I'll light Steve up there and I'll be like, "This
2:25:48
is how I wanted it to look all along, but I run  six cues. I don't want to update six cues. I want
2:25:54
to update the originating cue of the scene."  That's the premise behind update originating.
2:26:04
Next, simpler buttons over  here. When I make changes, the revert changes button appears. And all  that does is un-yellow anything I yellowed
2:26:16
and return it to where it was before I  clicked on it. Clear all is all at home.
2:26:28
I feel about clear all the way I feel about the  reset button. Only click it when you mean it.
2:26:40
Next,
2:26:46
I want to talk about over time just a  little because this is a nice little a little nice. This is sneak. All right.  11 through 15 at full. That's fine.
2:27:03
But 11 through 15, maybe I'd like them to fade in.  So I type 11 through 15 at full. Then I hit tab
2:27:14
over time five. Then enter. Just a little bit  gentler. Right. So if you're in the middle of
2:27:23
a scene in front of an audience and you're like,  "Oh god, someone's wandered off into a different area. They should be lit. Oh dear. Oh dear. 16 at  full over 25 seconds. Let's just creep that in so
2:27:36
that no one notices how wrong I was about that  light not being up or so that it feels as though
2:27:42
we have now decided to draw your attention  to that wandering actor or whatever, right?
2:27:52
Just a nice little tool.
2:27:58
Um over here we have an opportunity. We have  a choice. We can look at all the lights in the
2:28:04
patch or we can only look at the lights in the  patch that currently have levels in cues in the
2:28:11
workspace. So here's all my lights and here's  my lights that are used. The limit that this
2:28:19
provides is if I haven't used a light yet,  I won't see it. So I go to all and I'm like,
2:28:28
"Oh yeah, there is a light 230. I'm  just not using it for anything." But that doesn't mean I can't control it. It  still exists. It's just hidden from view.
2:28:45
That's all unused. And then the  other thing you can do here is choose whether you're looking at sliders or tiles.
2:28:55
tiles for a lot of folks can be a little  easier on the eyes, but also it can be
2:29:02
a little more difficult to parse and it  takes up more space. When you're in tiles,
2:29:08
the regular QLab behavior of click  and drag or click and type applies.
2:29:21
Yeah.
2:29:28
And you can still select a  fixture and get its virtual parameters in the sidebar in tiles.  It's really just a matter of taste.
2:29:41
Sliders work for me. And the reason that we prefer  horizontal sliders is so that the list can get arbitrarily long without a scrolling problem or  a wrapping problem or a layout problem. Right?
Subcontrollers
2:29:58
Subcontrollers are the next thing I  want to talk about. A subcontroller is a proportional control over a group  of lights. Used to be called submasters.
2:30:09
Still is on many fixtures. That's a word I'm  trying to get rid of from my vocabulary. So, it's a word we're also trying to get rid  of from our vocabulary as a group. The way
2:30:19
a subcontroller gets made in QLab is by taking a  light cue and ticking the box use as subcontroller.
2:30:30
The values recorded in the light cue are what those  values will be when the subcontroller is at full.
2:30:40
When you reduce the subcontroller, you get  a proportional reduction of those values.
2:30:46
You can of course always go and change  something individually. So I can use the sub to get lights to sort of a mixture  that I like, but then reach in and tweak.
2:31:02
Make sense? Subcontrollers can also be MIDI  controlled by a MIDI controller. Yeah. Salute.
2:31:10
You can put one light in multiple subcontrollers  and then it's on you to not do something weird
2:31:15
with the multiple subcontrollers at  the same time. When you record a cue,
2:31:22
it does not record the value of the subcontroller  into the cue. It records the value that the
2:31:27
subcontroller sets the lights to. So the  subcontroller itself is just a control.
2:31:34
It's not an actual um it's not an imaginary  light. It's not an imaginary group. Yeah.
2:31:46
DCA for lights. It's a DCA for lights. It's  really well put except for the fact that on
2:31:52
a on most consoles you can control the per  position of a DCA in a scene. But it's the
2:31:57
right idea. I like it a lot. All right. The next  thing I want to talk about is my actual favorite
Light language - pull
2:32:09
part of the lighting language which is pull.  So pallets and presets are a powerful lighting
2:32:18
design tool that many folks use in their um  in their travels. A palette by convention is
2:32:27
a collection of information that cues can draw  from. So, if you set all of your moving lights
2:32:34
to a specific focus and you like that focus and  you intend to reuse that focus for multiple cues,
2:32:40
you record a focus palette and then individually  on a cue by cue basis, you can say, "Hey, all my moving
2:32:47
lights recall from that focus palette and save  that in the cue." QLab, just like subcontrollers
2:32:55
are made of cues, pallets and presets are made  of cues. So, I'm going to set all at home. I'm
2:33:04
going to take all my lights and I'm going to  use all the color controls of all my lights.
2:33:17
And I'm going to set them all as red as they get.  And I'm going to record all to the selected cue.
2:33:28
No mistake. I'm going to record all red.  Red. All color red. All color red. All color
2:33:41
red. All color red. All color red. Great.  I'm going to update the selected cue.
2:33:52
So all color that um for both my  types of lighting of my of color
2:33:58
mixing are going to be at full red in this cue.
2:34:07
This cue is now going to be number  A. And then for cue number B,
2:34:15
I'm going to say all.intensity intensity or  just all at full all color. Let's type equals cue A.
2:34:31
When I send everything back to home, when I run  cue B, it sets all lights to the intensity
2:34:41
on its own and it sets all lights color  to whatever the value is stored in cue A.
2:34:50
Cue A is effectively a color palette.
2:34:58
For cue C, I might say, okay, let's  just say 11 through 13 at cue B.
2:35:11
Wait, I think this has Yeah, there we go. This  had um stale data in it. So when I go to go
2:35:20
to black and I run cue C, cue C brings 11 through  13 at whatever they are in cue B, which itself
2:35:28
is intensity 100, color at cue A. So this is a  nested pull. C pulls from B, B pulls from A.
2:35:40
You can also pull proportionately.  Lights red at cue A times.5.
2:35:49
scales the color value to 50% of whatever was  stored in cue A. Pull in the lighting language is
2:35:58
the way that a light cue can be used as a palette  without needing a distinct type of information
2:36:05
called a palette. So when I use QLab for lighting,  I make sets of pallets which are just cues with
2:36:12
different color combinations. I like different  intensity combinations. I like different beam positions, focus, whatever. They don't need to be  categorized. And similarly, a cue, which is a
2:36:23
palette, could contain all kinds of information. I  could have pan and tilt and intensity info in here
2:36:29
and then just pull color, right? All color pull  from a. So that selectivity allows me to be more
2:36:40
flexible with the pallets. uh more flexible than  pallets would permit because in existing consoles
2:36:48
you can have lighting color pallets which can only  contain color information and then focus pallets
2:36:54
which can only contain focus information and if  you want to combine them you have to make a preset which is a combination of a palette and a palette  instead we just say record a cue it has data
2:37:04
pull out all the information from that data from  that cue or pull out only certain information if
2:37:10
I see you I'll be right with you If after you've  done that pull, we change the source information.
2:37:24
The next time you run B, you get a  different color because it's still pulling.
2:37:34
If you want to guard against that, you can  say, "Well, I'm going to pull from that cue, but if I change my palette later, I don't want this  cue to change. This cue should always be this pink,
2:37:45
no matter what." You can click the expand button,  and it expands the pull out into a set of commands
2:37:54
that are actually the constituent commands.  And so now this QLab no longer pulls from QLab to
2:38:03
get these colors. These colors now live in this  cue. What's your question? Uh might be question,
2:38:13
but I'm sure it's not. Uh so you could put  all of like your cue pallets in another list, correct? Absolutely. And for tidiness, I  certainly would. I'd make a cue list. I'd
2:38:23
fill it up with pallets and then I'd keep  it unfolded in the sidebar so they could
2:38:29
refer to it quickly. And you would build  um tilt pan palette the same way like you
2:38:37
just select parameters save it and then you  Yeah. So let's go and find this moving light.
2:38:46
Are you there? Are you there moving light? It's  me, Sam. which means you can have one cue that
2:38:53
focuses a spotlight on a chair and have every  other cue pull from that so that if that chair
2:38:59
ever moves, you just have to update it in one  place. And within that cue, I can choose to save
2:39:04
just position data. I don't want any intensity or  colors like this. This little bit of information over here, this is just for pointing the light.  Yep. And then I can bring that in and then add
2:39:13
my own stuff on top of it. Yep. Exactly. You can  to repeat it for the stream just in case it was
2:39:18
hard to hear. You can store just position data in  the cue. No other information, just that tiny
2:39:24
little piece of data and then refer to that data  from all the other cues. I'm sort of remarkably
2:39:31
bad at this because the light is hung upside down  compared to the um joystick. There we go. So far,
2:39:42
dude, tell me all about it. Invert. Absolutely.  invert pen and invert tilt right here real quick
2:39:49
would be really really really helpful. So  I've made this. All right, I've got that um fixture now. It's in this sort of nice  bluey guy. It's got excellent definition of
2:39:58
your shoulders there. Good cheekbone angle, too.  Actually, this angle is really really nice. So I'm
2:40:05
going to record new cue with changes. And a new  cue with changes is everything I changed. Right.
2:40:13
So I've got 100.intensity, intensity 100 color 100  zoom 100 pan tilt but I want I might not want this
2:40:19
palette to contain that color or that intensity.  So I could kill those commands out of here or
2:40:29
I could just make a new cue. And in that  new cue I could say 100 dot zoom at cue V
2:40:41
and 100 pantilt at cue V. And that only pulls  the zoom and the pant tilt data out of cue V.
2:40:51
Or I could instead say no, I'm never going  to want to recall that intensity. I'm never going to want to recall that color. And  then here I can just say, hey, 100 at QV.
2:41:07
And it's going to pull whatever's  in there. When I expand it, it shows me it indeed pulls the  pan, the tilt, and the zoom.
2:41:19
For me, pull is like the bees knees. That's  that's the whole that's the game. That's why we're here for me. And to use a cue as a  subcontroller or to use a cue for pulling,
2:41:31
it needs to have a cue number. It's one of the very  rare cases in QLab where a cue number is mandatory.
2:41:37
And it's up to you how to make your cue numbers  convenient for you, right? You could make them
2:41:44
all, you know, you could structure them in some  way that's easy to remember or whatever. Yeah.
2:41:49
with some differences in like specifics but this  functions similarly to like a recall from key on
2:41:55
like an etc language I suppose. Okay. Pull is  recall from. Gotcha. Yeah. But now forgive me
2:42:03
does recall from copy the values out of the palette  or does recall from say get the values from the
2:42:09
palette every time the cue runs? I think it's  yeah because there's like make absolute. Yes.
2:42:16
Which means okay now break the link. So recall  from is pull and make absolute is expand.
2:42:27
There's another hand. Yeah. Can your numbers  have dual like C1 for color palette one or P1 for
2:42:35
position one or something like that? Yeah, great.  No problem. Or even C do one or whatever you want.
2:42:41
Make some structure that makes sense to you.  Renumbering your cues will break existing poles.
2:42:50
So you have to know to go into the old cue and say,  "Oh, actually it's not V anymore. Now it's C.1,
2:43:01
which is fine. I've been um having a hard time getting focus  out of the levels tab in lighting cues. In most
2:43:14
other cue types, if I change the selection by  using command up or down or the plus or you
2:43:20
know most of the time that pulls focus to the cue  list, but focus seems to really want to stay in
2:43:26
the levels tab of lighting cues. You're  doing you're doing command it's posing.
2:43:35
Okay. I don't know if that's a  choice or not, but if it is a choice, let's examine it. And if it's not a choice,  I found a thing that's not a choice. Yeah.
2:43:46
Okay, how we doing? Is there anyone here who  thought they might want to use QLab lighting
2:43:53
who now feels like they're ready to? Great. I work  with QLab lighting side by side with etc lighting
2:44:04
every summer. Right. I I teach at a performing  arts uh visual and performing arts summer camp. So all of our performers are between 11 and 17.  And um we do 19 fully produced works in eight
2:44:16
weeks. Theater, musical theater, dance, music, uh  sketch, comedy, improv, etc. And we use QLab not
2:44:29
most of the time, right? Most of the time we have  an ion XC20 and some of the time we use QLab and we
2:44:38
used to rent an element um before they discont... the  the the company that rents our gear discontinued
2:44:45
carrying an element. They now they give us an ion  which is great. And we found that the shows where
2:44:52
we wished we had something better than the element  in the past QLab's still not right for those shows.
2:45:00
But the shows where the element just got us along  just fine, those shows we can use QLab for and get
2:45:05
along just fine. So by my own sort of description,  I think QLab slots in nicely below etc's main
2:45:14
product line. I would rather use QLab than a color  source console. Personally, right, I would rather
2:45:20
use QLab than a two scene preset. But if your show  needs a hog, it will still need a hog. QLab's not
2:45:27
for you right now, right? And that's okay. I think  that's okay because here's the thing that uh an
2:45:34
element can't do is fit in my backpack. Yeah. What  are some of the things you ran into that like the
2:45:44
element should do? I had a hard time moving fast  with color changing fixtures on the element. I
2:45:52
had a hard time moving fast with moving lights on  the element. I didn't I I could get done anything
2:46:00
I wanted to get done. But that's true in QLab as  well. I can get anything I want out of a moving light in QLab. I just can do it well I can't but  my colleagues can do it dramatically faster on an
2:46:12
ion and we have one night of tech. So dramatically  faster really matters to us. Um um something that
2:46:23
QLab did for us at the camp that worked really  well is we had a rehearsal space that was left unattended and we did something we use something  that I haven't talked about yet which is cue carts.
Cue carts
2:46:37
A cart is an alternative to a cue list which  displays cues in a grid. There are two differences
2:46:46
between carts and lists that are important. The  first difference is carts cannot contain groups.
2:46:53
And the second is carts don't have a play head.  Other than that, carts and lists are essentially
2:47:00
the same. And you're right, like other than that,  other than that, Mrs. Lincoln, how did you enjoy
2:47:06
the play? What I'm trying to point out is that  the grid of buttons in a cart are not buttons for
2:47:16
cues. The grid is a grid of cues. These are cues.  They're not buttons that start cues. Does that
2:47:26
make sense? So, in this unattended rehearsal  space, I made a cart and I made light cues.
2:48:22
And now with QLab left in show  mode in that rehearsal room,
2:48:30
anyone could walk up, grab the mouse and turn the  lights off in the rehearsal room. Anyone could
2:48:37
walk up and grab the mouse and get to work in the  rehearsal room. When the rehearsal room was then
2:48:43
instead used for some impromptu performances,  I just made a few more cues that were a few basic looks. Anyone without consulting anyone,  without getting any lighting folks in the room,
2:48:52
without getting any management in the room could  just click these buttons and when they liked how it looked, that was their show. And that is  hard to do on the element. It's not impossible,
2:49:03
it's harder. So for me, for this guy,  that is like that's the sweet spot, right?
2:49:12
uh especially when you put this cart on a  touch screen because then you just take your your
2:49:18
uh capacitive mouse stick finger and go bop,  right? That's the game for me. I suppose it's a
2:49:29
good time to talk more about carts, though, since  we've brought them into the room. When you have
2:49:36
a cart selected in the sidebar, the inspector  gives you three tabs, basics, and triggers like
2:49:42
everything else, but also a grid size control.  You can have up to 15 by 15 cells or down to one
2:49:56
by one. QLab will not let you make it smaller than  the current number of cues in the cart requires.
2:50:04
So one by two is a minimum right now because  there's two cues in here. If I select and delete
2:50:09
these cues, I can get the cart down to one by one.  One big button. That's for the cruise ship. Go.
2:50:22
Cues in a cart have a second trigger action  that's worth mentioning. Right? If I um
2:50:39
uh if I set the second trigger action to  panic and I set second trigger on release,
2:50:46
when I click this cue and hold the mouse button  down, it plays. When I let go, it does its second
2:50:53
trigger action. That's rather different than other  cues, right? uh rather different than list cues.
2:51:03
So that can be uh you know uh it's called a  dead man switch was a terrible name in terms
2:51:09
of just just an ungentle name right but  it comes from I think from trains where
2:51:16
if you let go if the train operator has  a heart attack you would like the train to stop going please so it's called a  dead man switch because if the man is
2:51:24
dead then the switch switches I but I  find it very brutal and also only men and I don't like that at all in either way.  So, it is a a conscientious person switch.
2:51:37
How about conscious person switch? That's even  better. Uh attentive person switch, right? Oh,
2:51:43
cuz my little uh freak show operator  with the mouse that doesn't work very well. He'd have quite a problem with this  button as well. Anyway, I'm sorry. Please.
2:51:52
So just asking about the mouse click. We  don't have a play head previously. Space
2:51:58
bar will activate the selected cue  which is very obvious some of the time but not
2:52:09
very obvious some of the time. When you're  in show mode and there's two cues, nothing selected. When you're in edit mode, you see this  highlight. The selected cue will be triggered.
2:52:24
But there's a shortcut, which is Oh,  no. Never mind. I take back what I said.
2:52:31
Ah, there's a quirk. If the cue was selected when I  went into show mode, it stayed selected. Anyway,
2:52:38
yes, the answer is the spacebar doesn't really  do anything. The point is that you individually interact with cart cue cues with the mouse with  their hotkeys or their MIDI triggers. Or if
2:52:49
you have a touch screen attached to your  Mac, that's great. Or when we'll talk when we talk this afternoon about QLab Remote, although I  don't know, are by show of hands, are people um
2:53:01
extra eager for lunch or ready to keep going for  a while? Eager for lunch, hands up. Ready to keep
2:53:07
going for a little while? Hands up. No opinion.  Hands up. As my chemistry teacher used to say
2:53:13
in eighth grade. And for everyone who's afraid to  raise their hand, would you please put a different body part in the air? All right. Um, I do not  want to talk about rubidium this afternoon. Um,
2:53:25
uh, sorry. Sorry. Really went far a field  there. All right. Well, maybe we'll talk
2:53:31
about QLab Remote shortly, but QLab Remote  is a great inter-actor with carts as well. Um
2:53:42
uh so yeah, the carts can't contain group  cues. That's one big limitation. There's sort of no user interface paradigm that we could  figure out that would make the most sense
2:53:51
uh to put a group cue in a cart. So if you want to  use a cart to start a group cue, all you have to do
2:53:56
is put the group cue somewhere else, make a start  cue that starts that group cue, and put that start cue
2:54:07
in your cart. Where did it end up?
2:54:14
Well, you get the picture
2:54:20
here. I'll make a start cue. Cut. I go  to my cart. Paste. Here's the start
2:54:28
cue that reaches out and starts  a group cue in some other list.
2:54:34
start cues, uh, carts full of start cues.  It's a really standard practice,
2:54:42
really normal thing to see. Folks who like  carts, sketch comedy folks, improv comedy folks,
2:54:50
rehearsal room that I was describing  with the light cues. Um uh I was prep,
2:54:58
uh they ultimately went a different direction, but  I was preparing a cart of like status indicators
2:55:04
that OSCQs were going to update and change for  the uh French castle where like they would have a
2:55:12
cart cue visible on a Mac that the uh the doesn't  could come in and say start the evening show
2:55:20
and then the cart would update with information  about which cues were running in which rooms and how things were going. They ended up not needing  that. It's not about going a different direction.
2:55:29
They ended up not needing that control, so they  didn't use it. But a cart is perfect for that.
2:55:34
Someone who's untrained in QLab just sees a bunch  of squares and they say stuff. Okay, that's nice and clear and a great showcase for cue colors. A  great place to use cue colors to differentiate.
2:55:47
Okay. Um, I want to make sure that I haven't  blown past anything in lighting that I wished
2:55:53
I hadn't. I don't think that I have. Um,  I started to talk about I've talked about
The light command light - grouping, command history
2:56:00
grouping lights a little bit. Um, but I  just want to make it clear. 11 at full,
2:56:08
fine. 11 through 15 at full  also fine. 11 15 16 also fine,
2:56:22
right? If you use the up arrow key while  your cursor is in the command line,
2:56:34
you go through your command history and the  right side of the equation is highlighted.
2:56:41
The idea here is when you're programming  lights for a indecisive lighting designer.
2:56:46
So let's say yeah 11 through 13 at  full. No at 80. Up 80. Enter. No at
2:56:54
50. Up 50. Enter. Right. Up goes up  in history of things you've typed.
2:57:07
Left and right moves your cursor down  goes to the next goes down in history.
2:57:16
So up and down navigates the history of  commands since you open the dashboard.
2:57:27
That I think concludes my lighting pitch. Is there anything you want to talk  about about lighting, Chris?
2:57:35
Great. Um, I guess I'll just wrap up  then by saying that the main advantage
2:57:41
of lighting in QLab is that all the  other powers of QLab are available
2:57:47
to you while working with lighting in  QLab. So let's look at a timeline group.
Timeline groups and using QLab's features all together
2:58:02
Here's a timeline group.
2:58:08
that um uh has a piece of music in it. That piece  of music, if we look in its time and loops tab,
2:58:17
has slice markers. Let's listen to it  for a moment. Mark, mark, mark, mark,
2:58:27
and so forth. Yeah. While it's true that I've  put them on musically significant, you know,
2:58:34
tempo significant. I'm not really just following  bars and beats, I'm following moments that I,
2:58:40
as a designer, want to highlight. Then  I'm going to take a series of light cues
2:58:49
11 through 15 dot color. Or let's do it this way.
2:59:01
Make sure I'm in my base cue here. Yeah. Okay, great. Now I'm going to select 11 through  15. Going to make a dramatic color.
2:59:16
Update selected. Now I'm going to make a different dramatic color.
2:59:30
and select the next light cue.  Update selected. Now the next one.
2:59:36
New color. Update selected. Next  one. New color. Update selected.
2:59:59
New color update selected. Okay. Now
3:00:09
look in the timeline.
3:00:21
Notice that for the audio cue that has  slice markers, those slice markers are visible in this interface as those little  green lines. When I select another cue in
3:00:32
the timeline and slide it back and forth, I  see a blue vertical line that coincides with
3:00:38
the start of every cue in the timeline group,  the end of every cue in the timeline group,
3:00:44
and the slice markers in every cue in the  timeline group. And those vertical lines are
3:00:49
magnetic. [Music] So using that magnetism I  can easily really easily align cues to the
3:01:00
slice markers and in that way let's get rid  of all of you. In that way I can run a group
3:01:12
cue a timeline group cue. Uh, let's shrink this  down a little so you can see it more easily
3:01:21
and have lighting events line up with sound  events without really any effort at all.
3:01:32
Now, I wouldn't call this necessarily  the most tasteful choice, but it does
3:01:38
get the point across, I hope. Works with  lighting. Also works with video cues
3:01:53
here. Individual groups that are yellow align  with marks that I've put in the base rain and
3:02:01
thunder cue. And each of those groups is  a little goofball emoji thunderstorm moment.
3:02:15
The thing that's easy is sliding sliding cues  around to line up with marks is otherwise
3:02:22
actually rather time consuming and laborious to  do without a timeline cue. And something that I find very difficult as a designer is to do things  that feel sort of humanly-tempoed and natural by
3:02:34
typing in pre-wait times. I find that even  if I try to type in random pre-wait times, I end up typing pre-wait times that feel sort  of stiff and mechanical. Here, I can just use
3:02:44
the natural evolution of the thunderstorm that's  in this recording as a motivating um structure to
3:02:51
lay out my cues. That for me is something that  um you know, talking about putting the all the
3:02:59
tools together, that's where we sort of start to  really see what QLab's best at. And that's a reason
3:03:06
why doing lighting in QLab can be um can make some  things that are hard to do other ways very easy
3:03:13
to do. Admittedly, there are other things that  are easy to do on other platforms that are hard to do in QLab. But this is one example where the  opposite is true. Now at this same performing
Timeline groups and show control (e.g. in a dance concert)
3:03:25
arts uh and visual arts camp where I teach when we  do the dance concert, I usually stage manage. The
3:03:34
lighting designer sits over there with the ion  and actually every dance is cued by a different
3:03:39
dancer. So the lighting designers designed a house  plot but every student who comes to design a dance
3:03:46
piece which has their and they all have their own  level of uh knowledge and history and skill. They
3:03:52
sit over there with the lighting console. They  work on their looks. The sound folks sit over there with a QLab computer. I sit in the middle  as the stage manager and I've got a computer open
3:04:04
that's using QLab collaboration which we haven't  discussed, but I can see their computer. I put
3:04:11
marks in the dance piece every time I hear the  sound the lighting design student say go. And
3:04:19
then I line up show control cues which allow the  sound computer to remote trigger the lighting desk
3:04:27
so that there's no possibility that because  that the lights don't happen on time. Right?
3:04:32
I don't want the poss the the I don't want my  ability as a stage manager to catch something
3:04:37
in one night of rehearsal to affect whether or not  the lighting design students vision is realized.
3:04:44
So, I use QLab's tools to enable me to produce a  completely reproducible series of events, which
3:04:51
the lighting and sound computer robots talk about.  For me, that's the kind of thing that I'm getting
3:04:58
at when I'm trying to sort of build these features  together and build these ideas together. Yeah. And
3:05:03
you do that with slices and OC triggers. I do  that with slices and OS triggers. That's right.
3:05:08
But I could easily do it with slices and light  cues or slices and video cues because all of
3:05:14
QLab's different tools all sort of boil down to  cues in a list or a cart. Any technique that works
3:05:21
for one can work for another structurally. Yeah.  Anecdotally, I find whenever there's a like who's
3:05:29
going to be in charge, lights or sound discussion  about how the network is going to work, I show the lighting team this in the waveform. they can just  pick where they want their cues to go and they
3:05:38
say, "Oh, you drive it." Yep. Yep. Yeah. Yeah. So,  um, the MIDI show control spec says clearly what
3:05:48
you must not do is have a device that just spits  out MIDI show control data willy-nilly at all
3:05:54
times. What you must do is have each individual  cue in your system optionally transmit MIDI
3:06:02
show control uh for itself or not. ETC broke  that spec. When you turn MIDI show control on,
3:06:11
every cue that goes on the console comes out of  the MIDI show control uh comes out of the the
3:06:19
con of the console as a MIDI show control message.  And in time, I have come to feel that that is the
3:06:25
correct move to break that spec. Often it is often  true that if the lighting console is just blasting
3:06:32
MIDI show control data out, then for example, the  video system can just listen for cues, respond
3:06:39
to the cues it cares about, ignore the cues it  doesn't care about. In QLab, if you want to use
3:06:48
QLab to send MIDI show control, you can take a MIDI  cue, go to settings, change it to MIDI show control,
3:06:53
and say the name, the number of the cue you  want. But sometimes it might be convenient to
3:06:59
have QLab behave like the lighting computer. So, we  also have under MIDI a MIDI show control broadcast
MIDI show control broadcast
3:07:08
option. With MIDI show control broadcast turned  on, you pick a MIDI patch, a message format,
3:07:16
and a device ID, and then QLab. Anytime a cue  with a cue number goes in QLab, a corresponding
3:07:24
MIDI show control message will be sent. So, if  you're not doing the timeline with the light
3:07:32
cues lined up to the waveform, but you still  want to easily remote control another device,
3:07:39
the MIDI show control broadcast is the way. If  you do want to do it this way, turn off MIDI show
3:07:48
control broadcast and instead everywhere I've got  a light cue here, add a MIDI show control cue here.
3:08:00
which sends to lighting general the device ID  of the EOS console and the cue number you want to
3:08:06
send and the cue list that it's in and away you go.  Sam, have you ever seen anyone doing it with the
3:08:15
timeline but say a memo cue with a number sort  of a nothing cue but broadcasting giving it a
3:08:22
number? Well, we've only had many show control  broadcasts for a short time, so I don't know
3:08:29
that I would have had the opportunity to see  that yet. But I suppose there is no reason we
3:08:36
couldn't just do a memo cue that does nothing.  Give it a cue number. Well, a cue number that's
3:08:42
not in this workspace somewhere. Leave MIDI  show control turned on. And now that memo cue
3:08:55
would cause lights 56 to go. I don't see any  reason why not. I don't know that I think of that
3:09:02
as a timesaver, but I don't know that I don't.  Yeah. Yeah. Um, so I was just kind of curious
Recording output from QLab
3:09:13
about like groups and timelines. Just looking  at this interface, I can see potential utility
3:09:22
in maybe a non live show um context for like a  sound designer working on animation or something.
3:09:31
Have you guys ever thought of um adding  like an export group as file format feature
3:09:41
um for I don't know like export to like wave  file or something for like a like a video file
3:09:49
with like audio interspersed in different parts  of the timeline once I've built it in QLab. What
3:09:57
would be the advantage of exporting it? Um, I  I guess I don't know like uh for for non-live
3:10:06
show context. So like maybe like uploading to  YouTube if you're like an animator or something or
3:10:12
um putting into like a like a film or something.  Yeah. Yeah. So just using QLab simply as an
3:10:19
authoring tool. Yeah, we thought about it.  Um, every time you add a feature to QLab,
3:10:27
you open the door to adding a bug to QLab, right?  So, yes, I see what you're saying. Um, and it's
3:10:37
got some interesting appeal to it. Let me show you  how to do it without us having to add anything.
3:10:50
First, I'm going to go to the internet.
3:10:56
And I'm going to find Siphon  Recorder and download it.
3:11:11
That's interesting. Why did you quit QLab?
3:11:32
Yeah. Why is it doing what it's doing?
3:11:39
Siphon Recorder is a really interesting piece  of software. It needs to install Rosetta.
3:11:46
Is that okay with you if I install  Rosetta on this Mac? Yes. Okay, great.
3:11:54
Rosetta. No, the Oh, yeah.
3:12:01
Siphon Recorder is a pretty  interesting piece of software which um allows me to record the output  of any siphon server. Okay. So,
3:12:12
I'm going to go into QLab video output devices  and I'm going to create a new siphon device.
3:12:31
It's going to be 1920x 1080. It's going to run at  60 frames per second. And it's called record me.
3:12:40
By creating a new siphon device, I automatically  create a new output route assigned to use that
3:12:46
siphon device. I'm going to tell siphon recorder  in a moment. Well, first I'm going to go to my
3:12:56
QClass stage, which you've been looking at this  whole time, and I'm going to add a third region
3:13:03
using record me. This third region is also  going to cover the whole stage. And now that
3:13:11
it's active, I can see that Siphon Recorder  is able to see it and will be recording it.
3:13:23
Remember my Snow White demo yesterday?
3:13:31
Going to get it all set up and then  in Siphon Recorder, hit record.
3:13:40
Now I'm going to run through my Snow White demo.
3:13:49
And she walks across the forest. I wonder  what I shall see. I shall see this pine tree.
3:13:57
We look at her a little more closely.
3:14:03
Rack to dopey. Rack back to  Snow White. And Iris out.
3:14:13
The end. Now I hit stop  recording in Siphon Recorder.
3:14:20
And here I have a QuickTime movie recorded exactly  as I made it, exactly as I performed it in QLab,
3:14:32
which I can save to the desktop.
3:14:43
So there we go. Done. On the other hand, siphon  doesn't carry audio. For that, we need to install
3:14:52
a piece of software which I knew for a fact  required a computer reboot to install. So, I didn't want to do the demo with that. NDI does  pass audio. So, I could have done all this with an
3:15:03
NDI output instead of a siphon output and used an  NDI recording app. Also, none of the NDI recording
3:15:09
apps that are free are any good, and I didn't want  to adjudicate that right now in front of a class,
3:15:15
but you could use NDI and use an NDI recording  tool. Yeah, there's a large video art mapping
3:15:22
installation a couple blocks south of here that  we are weirdly not associated with. Uh, that is
3:15:28
a bunch of projectors in different storefronts,  all made it exactly this way. They fired up QLab
3:15:34
on each projector, mapped it, played the recorded  it and they're using like ruggedized media players
3:15:40
to actually... little Brightsign players.  Brightsigns. Yeah. Yeah. Right. Because those are small and affordable and they don't  do anything other than play the video you gave
3:15:50
them. So there's not a lot to go wrong. Yeah. Um,  for audio recording, if you're doing audio only,
3:16:06
BlackHole is like Syphon for sound. Um,  BlackHole lets you install an imaginary 2-channel,
3:16:14
16-channel, or 64-channel audio device. When you  send audio to a BlackHole device, it just sits in
3:16:22
the computer waiting for another program on the  same computer to pull that audio out. So, BlackHole works just like Syphon, but for sound.  Um, I also have had very good experience with
3:16:37
Rogue Amoeba's Audio Hijack and Loopback.  I find that they don't work exactly the way
3:16:45
I imagined they would work. So, it  takes me a couple of extra steps to make sure I'm doing it the way I think  I'm doing it, but they are impressive.
3:16:58
Farrago is Audio Hijack wandering... is the  Rogue Amoeba folks wandering into the land
3:17:05
of QLab carts and wondering if they could do it,  too. And I'm sure it's fine, but it ain't QLab.
3:17:18
So without us doing anything differently in QLab, a  little bit of elbow grease and these tools, you'll
3:17:24
be right where you want to be. That said, I can  see how just somewhere up here hitting yeah record
3:17:33
output could be cool. The question is, can we  add that easily without adding an enormous amount
3:17:40
of hassle, overhead, opening the door to bugs,  causing who knows what kind of trouble? Right now,
3:17:47
we can say to someone who uses copyrighted  material in QLab confidently, oh, we can't
3:17:52
duplicate your material. So, you know, you play  back your own thing. We don't have anything to do
3:17:58
with copying it. But if we add a recording tool to  QLab, it's reasonable for an anxious person to say,
3:18:03
"Wait, you can record my stuff." And then there's  um built-in copy protection for video outputs in
3:18:11
Mac. And how do we interact with that? And it  just gets a little dicey. I'm not saying no. I'm not saying never. I'm not saying definitely  anything. I'm just saying adding recording tools
3:18:22
is a little bit more of a there's an ellipsis  after it. Further investigation required. Was
3:18:29
your hand up or were you just holding your hand  up? Okay, great. I I have a follow-up question. Uh I I may have missed it if I zoned out when you  were saying, but did you have a were you did you
Assorted questions and discussion about potential future QLab features
3:18:40
have a way that you wanted to use a recording  output that you were thinking of? Uh well, it was mostly just like a like a like an export  group function, I guess. So like in a lot of DAWs
3:18:54
um like Cubase, you can like set up a timeline  where you've got like the video file you want to
3:19:02
put the sound effects on like at the top and then  you can place the sound effects in the timeline
3:19:08
and different like audio tracks and everything.  And I just thought that the the timeline interface
3:19:16
uh like UI in cue uh QLab would uh lend itself to  being able to do that kind of uh sound design
3:19:25
work with a group export function. And I guess  I'm specifically thinking like the the export in
3:19:32
in your workflow, the export then goes into what  destination? Uh I I guess I don't know. I've got
3:19:41
friends who are animators who sometimes complain  about the DA interfaces that they have to work
3:19:46
with and um QLab just seem very Gotcha. Gotcha.  Gotcha. QLab has uh QLab's the only tool I know
3:19:55
of at all where it doesn't seem like the folks  who made it assume it's an audio tool that can
3:20:01
also do video or a video tool that can also do  audio. Right? Editing audio in Final Cut feels
3:20:06
like a punishment. Feels like someone wishes that  you couldn't. but admits that you have to. And
3:20:12
likewise, dropping a video file into Logic so that  you can compose your score to match the video is
3:20:18
a little bit like uh you can bring in one video  file and the start of the video file is the start of the timeline. That's the end. And if you want  more, go pounce end. Whereas in a timeline group,
3:20:28
it's really easy to put the video wherever you  want in time and the audio wherever you want in time. It's the only tool that's like that. So  maybe an animator who's gotten their animation
3:20:38
just like they like could then drop it into QLab  and use a timeline group to easily add sound to
3:20:44
their animation rather than using the generally  horrible audio editing tools built into their
3:20:51
animation software. Yeah. Or I was thinking  like a sound designer that gets hired by an animation studio who's given a set animation  to work with. Yeah. Could like very smoothly
3:21:05
incorporate the workflow from the group the group  timeline function lab into again this isn't a live
3:21:13
performance context so I know that's probably  well no I mean this is this is why I'm asking is because um uh it's it's always interest my ears  perk up when I hear someone saying oh I want to
3:21:24
use this tool for something and it's a little bit  outside of you know that the the vast majority of
3:21:30
folks are using it for live playback and that's  kind of the whole idea it's designed around. Uh, and so for for most folks, recording the playback  is is sort of um doesn't doesn't even really make
3:21:41
sense because the playback needs to be different  every night. You know, that that's part of the deal. Uh, and so, but there are plenty of tools  that I once I get comfortable with a tool,
3:21:50
I'll reach for it over and over again because  like I know how to work in that. I can make what I'm imagining very quickly and it might not have  been designed exactly for this thing I'm doing,
3:21:59
but I know how to get there with this other tool.  I'm not even talking about QLab at this point, although sometimes I mean because I am familiar  with this tool, this is often the one that I
3:22:06
reach for for off-brand stuff. So, so when I hear  someone saying, "Oh, I would like to I have this
3:22:12
other workflow that this could be a good fit for."  I'm really curious about that because it it's if
3:22:19
we're if we're not too many steps away from what  world you're living in, then that could be very
3:22:25
interesting to us to go, okay, wait, there's like  a group of people that might like to use this and just needs an export function. We'd like to  know more. So that's, you know, of interest.
3:22:44
Yeah. Right.
3:22:49
Yeah. Yeah. That right. That's that's the  flip side of like my like glib. Like, oh,
3:22:55
you want to spend $20,000 on a TriCaster or  you want to do it real quick in QLab? It's like, all right, but now I'd like to record the output,  please. Um, easy on that $20,000 TriCaster. What
3:23:06
do I do here? Well, you set up the NDI thing and  the recorder and the blah blah blah blah blah. But that's not fast. Yeah. Yeah. Yeah. So that's  I mean that's that's interesting. We I just had
3:23:17
a a Zoom call with someone who just started  using QLab because uh and they work in audio
3:23:25
broadcast trucks and they do the music for NFL  games and they had just dropped by one weekend
3:23:31
and like I'm going to try this thing out for the  next NFL game. I had never used it before and
3:23:36
um and so we got on a call with them to say hey  how did it go? uh there's a lot of stuff here
3:23:43
that you don't need obviously what what is the  stuff that you're really focused on or is there
3:23:48
you know what would it look like for this to be  exactly right for just audio broadcast trucks so it's like that idea too is there are there small  you know we don't want to corrupt what's there but
3:23:58
if there's if there's uses for it that it's very  close and just needs a few more adjustments then
3:24:04
that's interesting. Yeah. Yes. Going back to Is  there a way to add an image to the card? No. No.
3:24:17
Text is the name of the cue and the color is the  color, but there's all this space here which seems
3:24:23
like it'd be a great spot to put a thumbnail,  right? Yeah. It's something we've heard about before and I understand the appeal. I think it's  a good idea and I think um it would be nice to do.
3:24:35
Yeah. Plus one from QC class. Have you considered  nesting cards where you have like one at the top
3:24:42
and then populate specific cards at the bottom?  We I don't know if we've considered it or not.
3:24:50
I find every time any nested type of like when I  have a stream deck and there's a button for more buttons and then another button for more buttons.  Every time I get lost. So for me, I f like what I
3:25:02
would prefer this guy is I would like a cue in  QLab that lets me say, "Hey QLab, now display this
3:25:10
other part of QLab." I would like to say a button  that says, "Show me this other cart. Show me this
3:25:16
other list." Rather than actually nesting, I  would like navigation tools for me. Um, but I
3:25:26
don't know, maybe nesting, maybe I'm unreasonably  persnickety about this and nesting carts inside
3:25:33
carts could work since we can't put groups in  carts right now. I don't know how it would make like I don't know how exactly that would work  visually. Not necessarily testing, but like you
3:25:44
were saying where you select that and like let's  say you doing stuff that you could select camera
3:26:07
Yeah. Right. If this button is not a button  that does anything other than shows all the
3:26:13
buttons that belong to camera one and now this is  show all the buttons that belong to camera two or
3:26:19
scene one or scene two or whatever it is. Yeah.  And so, um, I guess the the sort of meta note is
3:26:30
make it possible to use a cart more  flexibly. Make it possible to use a cart
3:26:37
um as a full as a full interface to more dynamic  situations. That's appealing. It's appealing.
3:26:56
Yeah, it's appealing. It's appealing.
3:27:03
Um, I wanted to wait, there was another  hand I wanted to delay. I wanted to
QLab Remote
3:27:11
um um talk about QLab Remote because we've  gotten a lot of things. We've gotten close
3:27:17
to QLab Remote a lot of times. So, here's my  iPad running QLab Remote. I've connected and
3:27:27
we'll talk I'll show you how in a sec.  I can pick any of the lists or carts
3:27:37
and then QLab Remote is an independent control.  Right? So, here I am on the Mac. I'm looking at
3:27:46
this cue list. Remote's looking at this  cue list. But if this person hits go,
3:27:57
it's hard to do upside down. This person  hits go, they fight about what's next.
3:28:03
But if this person has a cue list full of cues and  this person is looking at a different cue list
3:28:09
full of cues that do not fight with each other. For  example, if I'm running a bunch of cues here that
3:28:16
are video and I'm running a bunch of cues over  here that are audio cues playing in the lobby
3:28:21
or whatever that that's not a fight. That's  collaboration, right? Likewise the cart. All
3:28:31
right, I'm just going to not do it upside down.  I'm going to turn it around and turn it back.
3:28:37
Cart's nice because it's really easy to  just tap. QLab Remote connects over Wi-Fi,
3:28:44
but it also uses Apple's um Groovy doesn't matter  how you're connected, you're connected scheme,
3:28:53
which I don't remember the name of. Bonjour.  It's not just Bonjour. It's another thing.
3:28:59
If you have a USB cable connecting your Mac  to your iPad, they know about each other and they speak over the USB cable. Continuity is  part of it. It's there like it's a bunch of
3:29:11
feature names that are all related and connected.  Ditto. If you put a USB Ethernet adapter on your
3:29:20
iPad and connect with an Ethernet network,  Gil Remote will use that instead of Wi-Fi.
3:29:26
So um the main knock against using QLab Remote in  a show connect setting in my opinion there's two.
3:29:34
One is a touch interface can be challenging in a  live production environment because something you cannot do is definitively put your finger ready  on a button and definitely not touch it while
3:29:45
not looking. Whereas a physical button, you can  gently rest your finger on the go button and be
3:29:52
certain you're touching it and not pushing it  and watch and now go. Right? That's hard to do
3:29:58
with the touch screen. That's knock number one. But  knock number two is Wi-Fi and Bluetooth are flaky
3:30:03
and we can't necessarily trust them at all times.  And the truth is um you can't. So that's why the
3:30:13
cable connection or an Ethernet connection can  be used to sort of knock that out of the out of
3:30:18
the equation. Ditto a keyboard for QLab Remote now  gives you uh you know a spacebar. So now I can hit
3:30:33
spacebar and now QLab Remote is behaving the way I  would expect. So QLab Remote with a keyboard and a
3:30:43
wired connection to your Mac, you should consider  it fully reliable. QLab keep QLab without a wired
3:30:50
connection to the Mac or without a keyboard, you  could consider it mostly reliable, mostly dead,
3:30:56
still slightly alive. Um, mostly reliable, still  slightly flaky, but there's nothing we can do
3:31:01
about Wi-Fi, right? Like Wi-Fi is Wi-Fi. Um on  a strong Wi-Fi network, you get good QLab Remote
3:31:07
behavior in terms of connection. Yeah. Is there  anything you can't do to the session remotely via the iPad? So interacting with uh the cue list at its  top level. Easily done. You can swipe to flag a cue
3:31:26
really easily or edit its notes really easily. But  there's also an edit button which lets you edit
3:31:32
the inspector and... not all inspector tabs  are available in QLab Remote. The ones which we were
3:31:39
able to definitely make without it being too much  of an enormous hassle or it being too weird or
3:31:45
making compromises. Um those are what's in there.  Notably, I want to point out that in object audio,
3:31:55
a fade cue,
3:32:01
which targets object audio, has Oh, dear. Give me a second. It's actually  very hard, I've discovered, to um
3:32:12
to look and press like this without  being in front of the thing cuz anyway,
3:32:17
it just is. Um so I'm going  to tap edit. Okay, a fade cue
3:32:26
with Oh, I don't have the most recent  version installed on this, I don't think.
3:32:31
Um, fade cues can control levels. Uh, you  can control the triggers tab, the basics tab,
3:32:37
the levels tab. Um, we have a path editor  going, but I'm not sure is it out now? I'm
3:32:44
actually not up to date on this. Um, it is  um a work in progress. The geometry tab is
3:32:53
there. The light levels tab is there. Most of the  inspector tabs are there. Not every single one.
3:32:59
What is um a couple things I want to point out  that I think are really especially groovy about it. Um this button lets you enable or disable  the buttons on top of the sidebar, the go button,
3:33:16
or the controls at all. So you can prevent  yourself from accidentally hitting go if you're
3:33:21
using it just to view. Um and um for me crucially  you can edit you can view audio map monitors here.
3:33:37
So you can use this as a monitor tool to look  at your audio maps and you can edit oh here we
3:33:44
go video stages. So you can do your warping by  turning on the grid, coming down from the booth
3:33:53
and standing where it makes most sense and using  your finger or a pencil. Yeah, for me that's the
3:34:01
big thing. Is that an additional expense or is  that something you can just use if you have QLab
3:34:08
Remote is free uh in readonly mode. There's an  edit the editabilities are an in-app purchase
3:34:17
and then there's a separate uh I think slightly  cheaper in-app purchase for the light tools which
3:34:23
are again a work in progress but the light tools  in QLab Remote are like a keypad version of
3:34:31
the dashboard. The idea is it's meant to sort of  act like a programming wing. Um, but it is it is
3:34:38
still a work in progress and something that we  that we would really love more feedback on to be honest. Um, because we've designed it the way  we've designed it, but it would be cool to know
3:34:48
what's working for people and what's not working  for people. Is it 49 bucks for the edit? I forget.
3:34:54
I It's 40. Yeah. And like 20 bucks for the light  editor, something like that. pricing iPad apps is
3:35:06
a real mystery and the app store itself is a real  monster and Apple is mean about it. Um, and it's
3:35:15
a hard it's hard to work with. Um, so maybe one  day uh when we develop a functional government,
3:35:21
we will go like Europe goes and allow uh and force  Apple to allow people to install apps other than
3:35:27
through the app store. And won't that be nice? But  until that day, we sell through the app store. If you need a refund, you have to ask Apple for it.  If you need customer service, ask us for it. Um,
3:35:39
that's a quick quick QLab Remote toe-dip. It works  on phone as well as um iPad. Honestly, when I was
3:35:48
running shows routinely, I would make a cue list  that was just for soundcheck that looked good on the phone. I'd take my phone, go down on stage,  and flip through my cues. Yep, yep, yep, yep, yep.
3:35:58
Everything works. Put the phone back in my pocket.  And that's all I use. QLab Remote for when I was routinely operating shows as a designer when I'm  doing video I use it all of the time to do this
3:36:10
all of the time I don't I can't think of a single  show that I've done um video design for where I
3:36:17
haven't used QLab Remote to help me align my stages  um for audio only shows as a designer what I'll
3:36:27
often do is give the iPad to my designer. When I'm  an associate, I go to the gear menu and I enable
3:36:35
readonly mode. And when the iPad is in readonly  mode, you can see things. You can't edit things
3:36:45
except you can flag cues and edit their notes. So,  I give this to Leah. Leah watches the run through,
3:36:54
flags cues, edits the notes, and then by the end  of the run through when she comes back to me,
3:36:59
QLab itself contains all the information I need to  develop a work plan for the next morning so that
3:37:06
we can have all those notes done by the time the  actors come in at midday. A pretty standard tech
3:37:12
rehearsal structure where I work uh in New York  is that tech rehearsal basically is from noon to
3:37:18
usually about 10 p.m. Um then we have notes just  sort of a quick conversation and then the
3:37:26
next morning until noon is the time to do those  notes and then the actors come in at noon and we
3:37:31
get back to work without them. So the the premise  behind flagging and noting being capable of being
3:37:41
available when you're in readonly mode, even  though it's not read only, is to facilitate making
3:37:46
use of the morning session before noon. What or  whatever version of that morning session is in
3:37:52
your way of working. Yeah. Okay. Yeah. Well, why  is it just kind of connecting in my head within
3:38:00
like the show to create within this So if say  there's a producer that's sitting at the um Mac,
3:38:09
it's also keeping time while I am directing  something, but there's someone doing the lighting cues via um the remote QLab. But of course  rehearsal, they'll be able to go through and do
3:38:21
everything like that. But would it be sufficient  to have like only one of them have an edit mode so
3:38:27
that no one gets over each other to like pressing  buttons and stuff like that while calls are being
3:38:32
made? Like would that be sufficient or would  it be like you're getting into something that
3:38:39
I want to spend more than half an hour on? Okay.  So the answer to that question is that like that's
3:38:45
a great question and the reason I think it's a  great question is because it opens doors to a lot of different avenues of discussion. So I don't  want to jump into it and not have enough time
3:38:55
to really go. So let's come back to that right  after lunch because that is the first topic I want to hit after lunch is collaboration. Uh which  I think is going to really float your boat. Okay.
3:39:08
Um um [sneeze] salude um pollen man it's it's it's it comes  for us all. Um I think actually we're at a good
3:39:20
break point. So let's do that. Let's break for  lunch. Let's come back at 145. Wait, 12:30. Yeah,
3:39:31
1:45. Slightly over an hour. We'll resume at  1:45 and we'll talk about QLab collaboration first
3:39:38
um which is um um going to be our first sort of  full team hands-on experience. So if you have your
3:39:46
Mac with you, you will be participating in this  next topic directly. Um yeah, the iPad is 40 bucks.
3:39:54
iPad is 40 bucks. Yeah. Great. The edit the edit  unlock. Um great. We'll come back at 1:45. We'll
3:40:01
talk about QLab collaboration. We'll talk about  workflow tools and then we'll go where the class leads us. And if you are following along on the  internet, your questions are indeed most welcome,
3:40:11
particularly this afternoon to guide us  through other unknown topics. Thanks so much.
Collaboration
4:53:16
All right, friends. Welcome back. I hope that  your lunch was nutritious and restful. Um
4:53:23
uh or at least tasty and recent. It's best  I can do. Um, we're going to talk about QLab
4:53:32
collaboration, which is um, another one of those  features in which the amount of work it takes to
4:53:40
make it does not really match up with the amount  of work it takes to use it or understand it. Um,
4:53:46
we spent a lot of time on this. We spent a lot of  energy thinking about things and I think we ended
4:53:51
up with something that is um that is like it feels  like no big deal and it is a big deal. That's what
4:54:00
I'm trying to say and I don't really know what  the words are for that but QLab collaboration uh the premise behind it is um in some contexts  it's easy to get um a lot of folks who are ready
4:54:15
to work on your show and you want to have all  those folks pushing on QLab at the same time right
4:54:21
in an educational environment when I'm at summer  camp I've got plenty of young individuals excited
4:54:28
to get their hands on QLab Um, but you can only one  person can only type on a keyboard at a time. One
4:54:34
person can only use the mouse at a time. So, QLab  collaboration is a way of multiple folks using the
4:54:42
same workspace at the same time from multiple  Macs. Now, that does require multiple Macs,
4:54:47
but as we keep harping on, the base model entry  level Mac is uh really really in in inexpensive
4:54:55
and for QLab collaboration any used Mac will do.  as long as it can run QLab 5. So quite literally
4:55:03
any Mac that runs QLab 5 is a worthwhile contender  for using as a collaboration tool. Going to do a
4:55:11
little tiny bit of terminology. Then we're going  to start playing. We use the terms primary and
4:55:17
remote when talking about QLab collaboration.  The primary is the Mac that's hosting the
4:55:22
workspace that everyone's working on. So this  Mac is the collaboration primary right now.
4:55:28
The remote is going to be all of you. Each of  you has a remote or a remote Mac or a remote
4:55:34
workspace, which is what the workspace window is  on your computer when what it's actually showing
4:55:40
you is a copy of this. Yeah. Connecting uh to QLab  using collaboration requires a local network or
4:55:51
any network and a VPN. Basically, if the two Macs  are able to file share or able to screen share,
4:55:58
if they can see each other when you open a new  Finder window and go to network, then you're good
4:56:06
to go. Some IT departments at some universities  believe themselves to be the most important
4:56:14
department at the school and they will have  rules. My advice as strongly as possible, I've
4:56:22
often said it is the natural enemy of the stage  hand and in the wild you will only find them in
4:56:28
a predatory posture against each other. If you are  making theater in an environment with managed IT,
4:56:39
buy your own network switch. Go to Staples, spend  the 200 bucks on your own Wi-Fi network switch.
4:56:48
Put a sticker on it that says not a network, just  for art. Promise up and down that you will never
4:56:55
connect it to the internet. And then don't use  the school Wi-Fi for collaboration or the school
4:57:02
network at all. Closed networks that belong just  to the theater are the road to success. Here
4:57:14
I'm going to go to workspace  settings. collaboration.
4:57:21
And I have allow collaboration turned off right  now, which means that no other computer is able
4:57:26
to burrow into my computer and connect to  this workspace. And I'm going to make sure everything's set the way I like before I  open that door. The first checkbox here,
4:57:36
allow ask before allowing a new collaborator to  connect, will pop up a message on my screen when
4:57:43
someone wants to connect. And it'll say, "Hey,  Chris from Chris Ashworth's laptop.local is trying
4:57:49
to connect. Do you want to allow that? And if so,  with what permission and I can say yes or no."
4:57:54
If I uncheck this box, anyone who knows how who  with a copy of QLab who's on the same network as
4:58:02
me can collaborate in. So with this ask box  unchecked is a great way to start the day
4:58:09
when you're working with a bunch of folks who  you've already planned out what you're going to do together. With it on, you have to click  sit here and click yes a bunch of times. Right.
4:58:19
The next checkbox is when in show mode, restrict  all collaborators to view only. If you recall
4:58:27
when I discussed show mode on the first day, I  said that while you're in show mode, you cannot
4:58:32
add or delete cues. You cannot edit cues. You  cannot move cues. And that's a safety precaution,
4:58:39
not so much a security feature. The truth is,  show mode doesn't belong to the workspace.
4:58:47
Show mode belongs to your view of the workspace.  So if I don't check this box, a collaborator
4:58:59
working from a remote might be able to edit  the show while I'm in show mode. That might
4:59:06
be on purpose. That might be something you want  or it might be something you don't want. So this checkbox allows you to have this switch affect  all collaborators and not just yourself. Yeah.
4:59:22
Each collaborator appears in this list. And  here as an example, Alec during lunch break just
4:59:27
tested to make sure that the network was correctly  configured to use collaboration. So we
4:59:32
saw the username of the person who collaborated  on their computer. We see their machine ID which
4:59:40
is a code that QLab generates that is unique  to QLab means nothing to anyone else but us.
4:59:46
Um this code is derived from some secret formula  of ours that hopefully uniquely identifies your
4:59:53
Mac and no other Mac. If you send your Mac to a  repair shop and they do certain repairs, it will
5:00:00
come back with the same machine ID. If you send  it to a repair shop and they do other repairs, it will come back with a different machine ID.  The value of the machine ID is meaningless except
5:00:12
as pertains to looking in collaboration and  uniquely identifying a computer and saying yes,
5:00:18
this computer is that computer and no other. And  it has to do with licensing QLab. So, if you're
5:00:24
having licensing troubles and you communicate  with us about that, we may ask for your machine ID so that we can look up in our license database  where is that machine appearing in our license
5:00:33
database and figure out what's going on with its  licensing. Yeah. Next, we see the IP address that
5:00:39
was most recently associated with that computer.  And then we have three check boxes for the level
5:00:45
of permission that we want that collaborator to  have. The first level of permission is connect
5:00:51
and view. When that box is checked, that means  that Alec on this machine can connect and view my
5:00:59
workspace. In keeping with the view, the readonly  mode of cue of uh QLab Remote, someone with connect
5:01:08
and view access only can still flag and un-flag  cues and edit cue notes. Excuse me, little hiccup.
5:01:16
If Alec has edit permission as well, he can make  edits to my workspace. He can add and delete cues.
5:01:26
He can move cues. He can change settings. He  can do anything except start cues, stop cues,
5:01:34
or change the location of the playhead. If Alec  has connect and view and control permissions,
5:01:43
well, he can start cues, stop cues, and move  the playhead, but he can't edit cues. There are
5:01:49
a few tweaky exceptions. I'm um it's it's too  long a list of things to be exactly conversant
5:01:58
about in a useful way. So start cues, stop cues,  and move the playhead is a good generalization,
5:02:03
but there are some little edge cases  about like dragging things around in a um in a dashboard and stuff like that. We'll  just sort of set that aside for now. And if
5:02:13
Alec has all three checked, then he has full  access to your question just before the break.
5:02:22
Let's imagine a scenario in a small theater that  works like a regional theater. You may have one
5:02:29
burly Mac in the booth that's hooked up to the  lighting, sound, and audio and projection systems.
5:02:36
Then you may have a lighting designer with an  assistant, a sound designer with an assistant, a projection designer with an assistant, a stage  manager, and an operator who's not in the booth.
5:02:47
So, the operator might use a Mac to connect  with just control permission. That operator can run cues, but can't edit them. Not because  we don't trust our operator because if you don't
5:02:56
trust your operator, fire them. Hire someone  you trust. Um there is nothing we can do here
5:03:06
to replace trusting your operator. Uh again,  because unplug, steal Mac, whatever. Um your
5:03:18
assistant designers might have edit permission but  none other, no control permission. That way the
5:03:24
assistant designers can work on the cues, but they  can't accidentally run a cue and trip up the
5:03:30
operator and the stage manager who are working to  get in a flow. Then the stage manager might have
5:03:35
just connect and view permission. They can see  the cue list. They want to be able to see what's going on, but we don't want them accidentally  editing something because their job is stage
5:03:44
managing. They're not supposed to be tinkering in  a theatrical environment where union rules dictate
5:03:52
what a designer can and can't do. These checkboxes  can help. Right? When I'm working on Broadway,
5:04:00
the designer is not really supposed to edit QLab.  It turns out that it's a little different in
5:04:08
every theater, but in general, the designer is not  really supposed to edit QLab. The assistant is only supposed to edit if they've been um taken off of  their assistant contract and put on a local pink
5:04:18
contract. Certainly, no one is supposed to control  cues except the operator. So, these checkboxes can
5:04:26
help you adhere to either union rules or local  custom or just, you know, generally keep things
5:04:32
organized so that the wrong person doesn't  accidentally trip up the other person. Wrong person. So, that no one trips up anyone else.  Yeah, I just had a suggestion. I'll talk to
5:04:41
you about it. But maybe it's a useful suggestion.  Um, well, I had an A2 at a regional theater that
5:04:48
I used to work at who uh did something really  useful for me. Um, which I I didn't wear a
5:04:54
headset while I was mixing a show. Obviously,  you were the A1 in this context. The A1. Yes, I was A1. I had an A2. We had a cue light system  for me to be able to fire things or whatever. It
5:05:03
was all fine except my A2 wanted sometimes to  be able to uh send a message to me uh without
5:05:11
you know, and he put some program on the show Mac  where uh I don't even remember what the program
5:05:17
was. It was something tiny and proprietary and  weird. Um and not weird. It was fantastic. It
5:05:23
was just um it might be that. It might have been  something else. And he was able to just like send
5:05:30
messages, you know, like flash flash messages in  that exact scenario where I'm like and he was able
5:05:36
to ask questions and things like that. I just am  thinking about this where it's like, oh, we can an iPad to like obviously you put a lot of  devices on this like maybe an A2 having you
5:05:47
know if I'm trusting an A2 to run my my sound  cues or something but they need to like ask me a question I'm not wearing a headset is there  I don't know maybe some sort of interesting
5:05:55
communication tool could be built into this I  think some form of comms built in might be nice
5:06:00
like text based yeah specifically for sound people  who need that you know it's a little tricky I've been try I've been trying to hack one together  inside QLab and it turns There's a couple of steps
5:06:10
we need to de develop in QLab lab before that's  possible. But I'm glad to have your um anecdote
5:06:17
that explains the scenario because it's useful. Um  yeah, I think something like that could be cool,
5:06:24
right? Could be useful. Second from the back.  Yeah. You know, and like putting making making
5:06:31
like a set of buttons that's like we have  a problem. Like a card. Exactly. where like they can pop in and say like issue with battery or  something that like they don't have to calm. They
5:06:40
can just you know No, Dave, that did not sound  good. Yeah, right. Exactly. Something weird, you know, like something, you know, even a bunch  of pre-press responses. Yeah. The show that I
5:06:49
talked about a few times now, the um I kept saying  the show that I did a year ago. I never titled it.
5:06:55
It's called The Hills of California. That's the  title of the show. um on the hills of California, we used uh a chat app so that our A2 whose  position was in the basement. Actually,
5:07:06
the A2 in the basement was monitoring CCTV and  monitoring audio, monitoring the microphones,
5:07:11
of course, and she had a set of buttons that she  could pop messages up on our A1 screen, just like,
5:07:18
"Yes, I heard that pop. Also, keep your shirt  on. I'm looking into it." Right. Um, and our A1
5:07:24
had a series of buttons that you could just reach  over and quickly click like, "Heard a bad sound. Go look into it, please, right?" Or like, you  know, principal battery dead or whatever. Um,
5:07:37
yeah, Groovy, Groovy, thank you for the input.  that there's a bit of a running joke in the
5:07:43
software world that all products if they live long  enough will incorporate a chat function which is
5:07:48
um you know there's a bit of a cautionary note  in that joke as well because it's sort of like does everything need a chat function and then  how many features of chat of chat software does
5:07:57
every product need uh so there's there's there's  pitfalls too but no no I mean I no I I only say
5:08:04
this to say that we have had the same thought  and even started putting together. You know,
5:08:10
it's easy to put together a bad chat function and  we have done that and then we went, well, we don't
5:08:19
want to ship a bad chat function. So, what would  it make what would it take to make it a good one?
5:08:24
We haven't spent the time to do that. But I don't  disagree with you that it could be helpful. It's just a question of do we do we choose when do we  choose to work on that and how h how good is good
5:08:35
enough to ship and all these kinds of things. The  park rangers at Yellowstone have a phrase that they use um when talking about the difficulty  of designing bear proof garbage cans that
5:08:45
there's considerable overlap in the intelligence  between the smartest bear and the dumbest tourist.
5:08:54
That's really good. The chat app that is good  enough to be useful is generally good enough to
5:08:59
cause trouble. the the chat app that isn't good  enough to cause trouble is generally not quite
5:09:06
good enough to be useful. So we have to find  the right bare tourist overlap moment uh for
5:09:12
but I I will generalize and I will say well let's  think not specifically about chat but simply about intercommunication and said that there's some set  of functions which you can imagine could be useful
5:09:24
for communicating between different collaborators  in some way I don't know you know let's just think
5:09:30
about it that could be useful and I hear that for  sure okay so we've talked about permissions. This
5:09:38
first row in the table, default permissions  for new clients. If this box is unchecked,
5:09:43
don't ask me before verifying. Anyone who connects  will automatically get these permissions. If I
5:09:52
want everyone to be able to connect for free with  connect and view permissions, I do that and then
5:09:57
I turn on allowed connections and then anyone can  just connect up and it's all good. I can then go
5:10:03
in and individually doctor's people's permissions.  So, let's do that. I'm going to turn on allow
5:10:10
collaboration connections. I'm I've turned off  ask before allowing a new collaborator to connect.
5:10:17
And I would like for those of you who wish to to  open QLab, go to the file menu and choose connect
5:10:24
to workspace. And you will see the connect to  remote workspaces window. And among the various
5:10:34
workspaces you see listed, you will see QClass  5 September 2025 PNS Voxel. That's this one.
5:10:48
Briana connected. Javvon connected Dan.
5:10:54
And you see what's happening here for me.  My list is filling up with the names of
5:11:00
folks who have successfully connected. I see  your username in parenthesis. I see the name,
5:11:05
the file sharing name of your computer. I  see your machine ID and I see your current IP address. If I turn off allow collaboration  connections, you'll all get booted off.
5:11:18
You'll see a workspace window with a purple title  bar and a purple ring around the go button. I hope
5:11:26
that purple titlebar window is my workspace on  your computer. You have independent view. You can
5:11:34
move around wherever you like. But I invite you  to look in the sidebar at cue list S06 collaboration
5:11:45
and for everyone to select some cue in this list  so that we can demonstrate what's going on here.
5:11:53
And in fact, just for the purposes of this demo, could nobody select the first  cue, the group cue except for me?
5:12:03
What does it say? Anything more than  that? Could not connect the primary workspace has denied the request.  Okay. So I I think I may be getting
5:12:14
the requests. Um so I have Zach's MacBook  Pro trying to connect to my workspace. Um
5:12:26
September is QCL class 5 September 2025 PNS  Voxel appearing in anyone's list of eligible
5:12:35
workspaces more than once. I don't see it. You  don't even see it once. Are you all on the Voxel
5:12:41
Wi-Fi? There's a different workspace that says  QClass 3. That's mine. Suspiciously. I apologize.
5:12:49
That's fine. But MG SAV JNB619 ML1 which is how  do people usually pronounce your name? Mason
5:12:59
Gro School of the Arts. So Oh, I see. There's  a system here. All right. Great. All right.
5:13:05
Four letters at least. VJM is the name of our  theater and then NV is Brown. Uh and then Yeah.
5:13:16
So everything there has a scheme to it. Excellent.  All right. All right. That's a great system. Yeah.
5:13:25
I'm hope. So for those of you who cannot connect, who how many is that? One two. You don't  see Do you see other workspaces? Yes,
5:13:35
I see pretty much your exact list. You may have  to quit and relaunch QLab because network changed.
5:13:41
Maybe I have had this open all day. Yeah. Let's  try quitting and restarting on your end because we changed the network configuration over lunch  to be sure. Is that right? Over lunch. Yeah.
5:13:53
I'm glad to hear that it's not what you  were worried about, Christopher, though. That would have made me very anxious. Yeah.  I jumped straight to the worst case scenario.
5:14:07
Super interesting. Are we all using QLab 5.5.3?
5:14:17
Let's find out if you do need to update.
5:14:24
It's truly peculiar. I don't know what the  answer is. I wonder if restarting your Mac
5:14:30
would make a difference. I guess relevant. Is  there an upper limit hypothetically to how many
5:14:37
different machines could connect to one? I've been  told that there could be, but I've done this with way more than this many people. Yeah, my current  I think high water mark is 64. It was chaotic.
5:14:53
Is there like a hardware like a software  limit in there? You can only do 128. No, no,
5:14:58
we have not we have not introduced a limit. If you  if you hit a wall, I don't believe that that it's
5:15:07
because we built it into QLab. Who's Lynn Wood? You  were connected and are no longer. Is that true?
5:15:26
I see. I see. I think that um you should try  restarting your Mac. I wonder if there is some
5:15:34
network. So, uh what's the most succinct  way to say this? The underpinnings of the
5:15:43
networking software built into macOS 10. Oh,  wow. I'm showing my age. Built into macOS.
5:15:49
The underpinnings are old and have some um choices  that no longer feel relevant. How How about that?
5:15:57
Is that a nice way to say that?  Um, and a restarting of the Mac will clear out some cached information  which might be standing in your way.
5:16:09
And while you're doing that, I'm going to  proceed with the demo. Yeah, I'm sorry.
5:16:22
Everyone else is on 12. We're all on 12. Yeah,  I did some network-y stuff behind the scenes to
5:16:30
bridge to separate. You bridge 12 to five or 12 to  six. Is there any sort of uh sharing stuff in the
5:16:37
settings of the Mac that would allow or disallow  this to happen? Well, let's let me show you this
5:16:43
in your computer. Wi-Fi. Wi-Fi should be on.  I'm going to show you this section somewhere
5:16:50
else because I'm not using Wi-Fi. You want IPv4  on using DHCP and you're going to want to make
5:16:56
sure that this IP address is 192.168.12. something.  Subnet mask is 255.255.255.0. Router is 192.168.12.1
5:17:09
and DNS server is either 192.168.12.1 or  at least 192.168 something or empty.
5:17:21
I just saw one more person connect. Right.  Just just I I updated to 5.3 restarted Mac.
5:17:28
I got it. Okay. Collaboration does  require the same version of QLab,
5:17:36
right? Because what if I've got something going on  on my QLab that your version of QLab can't support?
5:17:42
How do we show that information? Especially if  we invented it after your version was released.
5:17:47
Then how would we reach back in time and  tell that version this thing that we haven't invented yet? Ignore it. Don't worry. But  if I address if you enter an IP address
5:18:03
sometimes it's flaky is flaking on us. All right.  Okay. But airdrop always works. So I'm going to
5:18:14
proceed with the demo then. So here we are in this  workspace. All of you have connected with connect
5:18:21
and view permission and we see each other's  presence via these yellow dots. A collaborator is
5:18:30
highlighting a is has a cue selected. We can see  that with a yellow dot. If two of us are looking
5:18:36
at the same or more than one of us, Alec, will  you select the collaboration uh group cue? Now,
5:18:43
let's look down in the inspector. When I go  to the mode tab, I'm looking at the mode tab, but I see the basics tab underlined. That's how  I know that Alec is looking at the basics tab.
5:18:54
Collaboration was not designed with the assumption  that this larger group would be working together, although as you can see, it supports it.  So, it's hard to say all these yellow dots,
5:19:06
who's who. One of the things we'd like to do  in the future is allow some form of customizing
5:19:11
of this yellow dot. so that it is easier to  tell people apart. But that's down the list.
5:19:18
I'd like to ask you invite you now all to go to cue  list Z01 play space which is the next to last list
5:19:27
and in and now I'm going to tell you I'm before  I turn on everyone's edit and control permission
5:19:37
I'm going to talk to you about a design philosophy  choice that we made which is how do you deal with
5:19:45
permission to make changes how do you deal with  collisions of edits. One thing we could do is we
5:19:51
could make a very sophisticated set of rules in  the software that govern behavior. The other is
5:19:58
we could make some really basic rules and rely  on human level rules to govern behavior. And
5:20:05
so this is the way that we've chosen to go.  And it's the way that Google Docs works too, right? If we're all working on a Google Doc  together, I can type something, you can delete it,
5:20:13
and then I can say, "Please don't delete  it." And then you won't if you're nice,
5:20:19
right? We have decided let's not make it.  We thought about all right, should we make
5:20:24
it impossible for two people to edit the same  cue list at the same time? But we thought that was too restrictive. So I'm going to turn on edit  permission now. And I would like to encourage you
5:20:35
to please only edit cue list Z01. There's nothing  that I can do to force you to edit only cue list Z01.
5:20:47
But I'm hoping that you will. So now with that  edit box checked for everybody, you should all
5:20:56
be able to add and edit and change cues in this  cue list. But if anyone tries to delete a cue,
5:21:03
you're going to come up against one of our first  uh the the first of a small list of kind of
5:21:09
non-negotiable rules right now. In collaboration,  everybody has their own undo history. So if you
5:21:19
make a cue and then you make a cue and then  you hit undo, your cue that you created gets
5:21:24
undone. Your cue is left alone. When you hit  undo, your cue goes away. Okay, awesome. Right?
5:21:32
It's really confusing. If I make a cue, then  you make a cue, then you make a cue, then I hit undo and your action gets undone. That's very,  very vexing. It turns out that there are um a few
5:21:45
actions that really mess with our ability to have  this unique undo history and that is making cues,
5:21:51
deleting cues, moving cues. So while collaboration  is active, making cues, deleting cues and moving
5:21:58
cues is not undoable. They become non undoable  actions. Which means please hear me, please hear
5:22:05
me. Deleting cues cannot be undone when you're  collaborating. So get yourself in the habit of not
5:22:13
deleting a cue unless you are absolutely sure that  that cue is of no use to you. Instead mark the cue
5:22:30
or something, right?
5:22:37
Disarm it. disarm it and skip it. Oo la. Get  yourself in the personal habit of not deleting
5:22:47
cues unless you are absolutely certain  that you don't want the cue. Because
5:22:52
to undo making a cue even though undoing is  blocked is actually quite possible. If I make
5:23:00
a cue and I can't command Z undo the making of  it, I can still get rid of it by deleting it.
5:23:06
to undo moving a cue. Even though undo is  blocked, I can manually move it back to where
5:23:11
it was before. But to undo deleting a cue when  undo is blocked, there's no other way to do it
5:23:17
except to remake the cue from scratch.  And maybe you forgot or didn't even tell
5:23:22
uh couldn't tell wasn't you weren't sure about  all the parameters of that cue. So that's the
5:23:28
only little data loss potential and I want you to  be aware of it. The other thing that is important
5:23:34
to understand is as far as OSC messages and Apple  script messages are concerned only the cue only the
5:23:43
selection on my computer the primary matters.  So if you have a script or an OSC message that
5:23:50
refers to the selected cue or cues, it's the cue or  cues that are selected here that matter. Thank you.
5:24:11
um QLab. So a couple of things to talk about  other to that. This has nothing to do with
5:24:17
OSC. If I turn off OSC access in network,  collaboration is unaffected. Even though
5:24:28
OSC access has view, edit, and control permission,  and collaboration has view, edit and control,
5:24:33
they're different. It's just the same sort of  structure, but they're two different systems. Yeah. Um, we talked about undo and we talked uh  and we talked about how everyone has their undo
5:24:45
history, but actually everyone has their own  undo history in two separate ways. You have your own undo history in the cue list and you have  your own undo history inside workspace settings.
5:24:57
But in the light dashboard, we all share  one big undo history. Could someone please
5:25:03
open the light dashboard? I make a change. Would  whoever has opened the light dashboard hit undo.
5:25:14
No change. I'm sorry.
5:25:20
I'm making several changes. Are you seeing  it in your dashboard? And if you try to undo,
5:25:25
does it undo? No. Are other folks moving things  by hand? No. I think they're moving by undoing.
5:25:34
It's just slow. So, we all share one big undo  history in the light dashboard. And that is
5:25:41
because the light dashboard, unlike the cue list,  immediately affects real life. And so there is
5:25:49
no such thing as multiple states of possibility.  Either the light is on or is not on. Right. So,
5:25:56
we all share one big undo history here. Do you  want to say more? You have a No, I just noticed that this is the first time I've seen you teach  this class where you didn't give control command.
5:26:06
And was it because you didn't want people  distracted? The last time I did this class,
5:26:13
no, I'm teasing. Usually when Sam teaches this  class, he is given control commands, which means
5:26:18
that the entire section he just taught, there's  stuff flying around and flashing behind him on the screen. And I have a feeling that maybe he  didn't want to compete with that this time. The
5:26:29
teacher becomes the student. And I learned that  that makes it so I I was taught something early on
5:26:36
in my teaching history. If you have a handout to  give to the class, you give it before they leave,
5:26:42
not when they walk in. teachers in the room  by someone just went you teach. Don't give the handout out of the beginning. Everyone  reads the handout and ignores you. Don't give
5:26:51
controllability to folks. I'm going to be you  know who knows what's going on up here. Crazy
5:26:56
projection. I can't see it. It's not substitute  teacher day. I know who sits where. Right. Sorry.
5:27:04
Was elementary school not quite as scarring for  everyone as it was for me? Have I outed myself?
5:27:12
But you have discovered that you can control  lights in the dashboard without control permission, haven't you? And the reason is that  is an edit, right? That's not a cue that you're
5:27:21
running. That's an edit, right? I would like I  would like to like for me intellectually changes
5:27:29
made in the light dashboard qualify as edits.  Once we save them as a cue, running that cue, that's a control action. Yeah, I'm still going to  come in here and every now and then just fix it.
5:27:45
Unless you would like me to get seasick before  your very eyes. No, no, no. That's um I want
5:27:52
to talk about the license implications  of collaboration because this matters.
5:27:59
The primary allows um one unlicensed copy of QLab  to collaborate in So, if I'm here with a licensed
5:28:12
Mac and Chris has a Mac with no QLab license on  it, he can connect to my Mac with whatever access
5:28:23
permission I want to give him. But if Alec also  has an unlicensed Mac, he can only connect with
5:28:32
view only permission. So the door is there's only  one door open to an unlicensed collaborator with
5:28:40
edit and/or control permissions. You can have an  unlimited number of unlicensed Macs connect with
5:28:47
view only permission. Right? Your stage manager,  your ASM backstage, your A2 can all connect
5:28:54
without having to have a license just so they can  see what's going on. If your Mac has a license,
5:29:01
you can connect with full powers as long as I give  you full powers over here. Yeah. So, in short,
5:29:08
one person gets in the door for free. An unlimited  number of people get in with view only permission
5:29:15
and an unlimited number of people with their own  license can get in with full access. Crucially,
5:29:21
while collaborating, your computer behaves as  though it has my license. So, if I have an audio
5:29:30
license installed and you have a lighting license  installed and you collaborate into me, during the
5:29:36
time that you're collaborating, poof, you have no  lighting license, you have an audio license. The
5:29:41
idea is the primary license dictates what's really  going on. Yeah. Question. It was that. All right.
5:29:53
We tried to make this We tried to put this in the  exact sweet spot between being as permissive as
5:30:00
we possibly could while being able to make money  off of things that are of value, right? Yeah. In
5:30:11
the opposite regard, so let's say I have all three  lessons and you only have audio, but I want to do
5:30:17
some funky Can I just swap licenses and give you  my license and you give me yours and then like in
5:30:23
the Well, see what I mean? So, here's the thing.  Licensing in QLab is really easy to deal with as
5:30:31
long as you understand it. And it's easy to think  you understand it fully and you don't. So, let's
5:30:38
spend a moment so that you do. When I go to the  QLab menu, manage your licenses. When I sign in,
5:30:45
I can install or remove licenses that are in my  account. But if you come over here and you sign
5:30:52
in on my Mac, you can install or remove licenses  that are in your account. So if you travel with
5:30:58
your laptop to a theater, you've got the full  bundle license. You want to do whizbang video, but the house computer has only an audio  license. Your license the the the policy
5:31:10
from us on QLab 5 licenses is that your license  can be installed on two computers at once. That
5:31:17
is the end of the policy. In QLab 4, the policy was  you could install it on three computers at once,
5:31:22
but you had to use those three computers according  to a fairly specific set of circumstances. Now,
5:31:28
we just say install it two times. So, you can  come to a theater, come to the the theater's Mac,
5:31:34
sign in with your account, install your video  license, then sit down on the at the tech table,
5:31:42
collaborate in, do whizbang video. The  only thing I want to caution you about
5:31:47
is not forgetting to come back and remove  your license before you leave. Otherwise,
5:31:53
in an half a year when you're at another theater  wishing you could install your license there. Oh,
5:31:58
I left it at that other theater. We do offer  some license management tools that allow you
5:32:05
to remotely deactivate a license. You can go to  our website QLab.app, sign into your accounts.
5:32:19
Yeah. Thank you.
5:32:30
Oops. All right. Sign into your account. Go to  licenses. And look, here are my licenses. So,
5:32:41
let's view details here. I've got my video  license installed on my MacBook Pro and on
5:32:47
a Mac called the cue QClass. I could remotely  deactivate the QClass. The next time that Mac
5:32:55
connects to the internet and launches QLab,  QLab will holler up to the license server,
5:33:01
"Anything I need to know?" And the lesson server  will say, "Yes, you're done. Goodbye." Right.
5:33:12
Did I hear a inhalation? No, I was just I was  just remembering before I founded this company,
5:33:19
I worked at a computer security company  in Colombia and I was so computer security company and I was giving a um presentation in  a meeting and I did I did what Sam almost did
5:33:30
which is I entered my password into the name field  during the presentation in a room full of computer security experts. My office mate thought that was  so funny that to this day he uses that password as
5:33:43
his online name for every account he has ever made  since then. He's still trolling me about it. Ouch.
5:33:55
So you have some recourse if you leave  your license at the at the venue.
5:34:02
I have a lighting. I have a lighting. You have an  audio. We can merge our cars. We can't do that.
5:34:08
Sure. Leave my audio installed. Come over  here and install your your lighting also.
5:34:15
Yeah, you can have I could have as many licenses  installed as I like. Right. So, we sell rental
5:34:20
licenses. Rental licenses have a start date and  a duration. So, something that we get asked a lot
5:34:26
about is with rental licenses. Look, I'm doing a  show. I don't have enough money to buy a license.
5:34:32
I'm doing three weekends spaced out over the  course of a year. Three weekends, that's only
5:34:39
six days. So, can I buy a rental license for  each weekend only? Yeah, no problem. But it's
5:34:46
spaced out over a year and I don't want to think  about it in advance. You can go to our store and
5:34:52
buy the three rental licenses today. Pick the  start date of each of your weekends. install all
5:35:00
three licenses now and on the day in question that  license will wake up, do its thing and when it's
5:35:08
done it will fall back asleep and vanish. So you  can install as many licenses as you like and they
5:35:13
overlap. They don't conflict. Likewise, my audio  license, your lighting license installed, their
5:35:20
powers combined. Wonder Twin powers activate. We  do a show. It's phenomenal. Then you're done. You
5:35:25
remove your license. Leave mine. Go on your merry  way. Yeah. What time of day does a rental that we
5:35:36
were to purchase from you start midnight local  to the computer? Oh, to the computer. Okay. Is
5:35:44
that right? That's that's basically right. We  do put a little wiggle room in there just so that if you you know there's not a if you have a  rental license installed and you're doing a late
5:35:53
night show on New Year's Eve, it's not going to  stop working at midnight. You know, that kind of thing. So there's there's there's extra buffer um  that we don't get too like specific about because
5:36:03
we don't want people trying to abuse it, but we  we don't want your show to go wrong. So yeah.
5:36:11
So yeah, and also like what if your clock is  off by a few minutes? You know, as we discussed yesterday, it's probably off, right? So midnight,  which is how I generally feel at that time of day.
5:36:25
So, you know, fuzziness is appreciated.  Was there a hand up? No. Okay. Great.
5:36:33
So, why did we get to license? We  were talking about what license situation applies during collaboration. Right. So,
5:36:40
even if you all didn't have the demo licenses  that we set up for you on the first day of class,
5:36:47
you would all be at minimum able to view only  collaborate. And of course, as we all know, view only includes flagging and editing  notes. Someone's just testing. Well done.
5:37:00
And I have become very much in the habit of  putting if I have an available, excuse me,
5:37:06
if I have an available Mac, putting a Mac  in view only on the stage manager's desk,
5:37:12
right? It makes the stage manager feel nice to  know what's going on. It gives the stage manager
5:37:18
an opportunity to look over and see, "Oh gosh,  Sam is making cues at a blistering rate. I best not ask him right now if he's working. I already  know the answer. He is right." Um, it also helps
5:37:31
with my personal little pet peeve, which is a  stage manager calling hold when the lighting designer asks for a hold and calling holding for  sound when the sound designer asks for a hold.
5:37:42
Ideally, if they just see me blistering  away, they don't even need to call for a hold and we can just save a little tiny bit of  interpersonal conflict. Collaboration questions.
5:37:57
Have we addressed the scenario you were thinking  about at the beginning uh of lunch? Yeah, I find
5:38:04
this a really really useful thing. And in terms of  human level rules, when I'm doing a regular show,
5:38:11
I just have one cue list. If I have if I'm at at  summer camp and I have several campers in working
5:38:16
with me, I will simply say like, I'm going  to work on scene one, you work on scene two,
5:38:21
you work on scene three, and we stay out of  each other's way. It's not that hard. The
5:38:27
easiest solution to not accidentally editing the  same cue at once is do not try to edit the same cue at once. Look for the yellow underline  and the yellow dot before you go to town.
5:38:37
On the other hand, if someone's  doing something interesting, go find the yellow line and watch them, right?  So, it's a good teaching tool as well. Yeah.
5:38:48
Have you considered disabling the delete function  during collaboration or that feature, I guess?
5:38:59
No, honestly, I haven't. one that you can toggle.  Yeah. I think what we're what we'd like to do
5:39:07
uh and we were just talking about recently  in our one of our recent developer meetings is we want to take another pass at  those three things. Move, delete,
5:39:16
add, and just see what clever stuff we can  come up with to either make them undoable.
5:39:23
There's there's a fundamental conflict where  you there's some operations that if two people
5:39:28
do them, there's it's an undefined thing to  try to undo it, you know, like what if Chris makes a group cue and I put an audio cue in it,  then Chris deletes the group cue and I now what?
5:39:40
Now what? So there so there's just some there's  just some logical conflicts in some scenarios,
5:39:46
but not all. Uh so we want to see if we can  just make that thing work better. So the the
5:39:53
underlying question is like could this work  better or could you make it a little... the answer is I think we could. I don't know  exactly how but I agree with the question and
5:40:03
we're interested in continuing to work on  that part. I do like the idea of at minimum
5:40:12
introducing one more step of friction before  deleting cues while collaborating. Yeah, I don't
5:40:25
list always deleted or cues to delete. Yeah.  And sort of similarly for undoing uh a deletion,
5:40:35
if the if the undo of a deletion doesn't have  anywhere to go, well, we could put it in this sort of holding area of like this thing came back from  the dead and it doesn't have a place to live now,
5:40:43
but it's over here, so you can put it where  you want it. You like that? That idea. Yeah.
5:40:48
So I here I'm going to jump ahead in the  class a little bit. I have a list here, cut cues. And in my scripts list, I have a  cue cut selected. And what this script does is
5:41:05
moves cues to the cut list. When I type the hotkey  trigger, Ctrl X. So if I want to delete this cue,
5:41:16
I hit control X and that cue is moved to  cut cues. My script also prepends the
5:41:25
cue number with a little X. And the reason  I changed that is, yeah, I'm moving you.
5:41:35
I the reason I did that is because I used  to have this script and I had, you know, a cue number and then I deleted the cue and  then the then the designer who I was working
5:41:44
with wanted to make a new cue with that cue number  and I couldn't do it because that cue number is
5:41:50
taken up by a cue in my cut list. So now when  I control X cut a cue in the cut list it has
5:41:56
the little letter X prepended which means if I  cut another one it will be XX569 and so forth.
5:42:11
So the we could consider a policy in which  while collaborating deleting a cue just
5:42:20
basically does that. There are worse ideas  and like harder to understand ones. Really
5:42:26
the thing is we want to make a thing that when  it happens no one's like why on earth did QLab do
5:42:31
that right? We want to try to avoid that so that  you don't get mystified while you're in the middle
5:42:38
of trying to do a show and there's a director  there who's tapping their foot wanting you to get on with it and you're like, "Oh, well,  my QLab warning." And they're like, "Words,
5:42:47
don't care. Theater making busy. Let's go." Right?  Like that happens. And um we want to try to make
5:42:55
something predictable and easily usable. So, okay.  Yeah. So, is there a way in collaboration? So,
5:43:06
let's say you have an associate designer  who you say, "Hey, this sound effect isn't
5:43:11
working. Go find me a new one. Go find me a  new doorbell." Yeah. That associate designer
5:43:17
is collaborating with you. How do you get around  them not being able to use your file? You know
5:43:24
what I mean? Great. I do. So let's start let's  let's go back one step and talk about targeting
5:43:30
uh making targets uh selecting targets for cues  which have file targets while collaborating. If we
5:43:36
have an audio cue and I want to set the target  I get a window that shows me all the files on my
5:43:42
computer. But if one of you selects this cue,  this audio cue and tries to select a target,
5:43:48
what you see is an interface that we built, which  is basically just all of the media inside the
5:43:57
folder that contains the primary workspace, which  is pretty groovy, right? If you want to if someone
5:44:05
wants to set the target of this file, it's not  that hard to do as long as one of the target as
5:44:11
long as the target that you want to set is already  inside my audio folder here. So the answer for now
5:44:18
is that your associate should also have a file  sharing connection open onto this Mac and then
5:44:26
they can drop a file into the audio folder here  and then when they open up the target interface
5:44:33
within QLab that file that they dropped in using  file sharing will appear within that list. Does
5:44:41
it also work in conjunction with Dropbox or Google  Drive? In that regard, Dropbox and Google Drive
5:44:49
and iCloud Drive and Box.net and all of those  are all two-edged swords, multi-edged swords,
5:44:56
swords with many shapes. Specifically, Google  Drive is my enemy. When you take a QLab workspace,
5:45:08
um, any file on your computer, among other  truths about it, has a thing called a UYU ID,
5:45:15
um, which is a hypothetically completely  unique code that identifies that file like
5:45:22
a license plate, right? Every license plate of  every car is hypothetically completely unique.
5:45:27
It has its own combination of letters and numbers  and a state and there's not two the same anywhere.
5:45:36
But all the DMVs talk to each other. So that's  how that's insured. Every computer in the world
5:45:43
doesn't talk to each other, at least not all the  time. So when a file is created on my computer,
5:45:49
it gives it a UYU ID. When a file is created  on your computer, it gives it a UYU ID. there's a small possibility that they picked  the same random number. It's not a number, it's
5:45:58
a number and a letter combination that is very not  likely to collide, but it happens. So, when I copy
5:46:04
a file from my Mac to your Mac, one of the things  that happens is as it arrives, the Mac says, "Hang on, I've already got a file with that UU ID.  I will give you a new one." So, files secret code
5:46:17
name can change when they move from computer to  computer. When you put a QLab project in Google
5:46:26
Drive, Google invisibly duplicates or sometimes  reduplicates or deletes a file and remakes it from
5:46:34
scratch or does all kinds of nonsense. Whereas  when I whereas when it arrives on your computer,
5:46:40
some of those UU IDs have changed and some  have not and the QLab workspace can easily lose
5:46:45
track of the link that it had to all of the file  targets. Something unique about how Google does
5:46:52
it makes that much more likely than any other file  sharing provider. This guy, me, when I have put a
5:46:58
QLab folder in Dropbox and pulled it back out, I've  never had a problem. Same with iCloud. But Dropbox
5:47:08
and iCloud have both recently started pushing this  feature in which files which appear to be on your
5:47:14
computer are in fact not on your computer. They  only get downloaded when you ask to view them.
5:47:21
And when a file is in that state, QLab may not know  whether or not that file is valid and either will
5:47:28
or won't behave nicely at the moment of it being  asked to play that cue that targets that file. Yeah,
5:47:35
just uh um if you if you want to use Dropbox to  transfer the files, that's fine. just get them out
5:47:44
of Dropbox before you're really using them is I  think the the because even though Apple says that
5:47:51
we ought to be able to ask the computer whether  the file is really there, they're lying. And so
5:47:57
one of the things that we're seeing relative we're  seeing an increased incidence of QLab freezing or
5:48:04
having problems when it tries to access a file  and the file isn't really there and and everything locks up and it doesn't know what to do and and  you know we've sort of dug into this to go well
5:48:13
surely we could ask the operating system is the  file really there and you'd think you'd think
5:48:18
you could ask that and get a real answer but  instead the operating system just says don't call me Shirley. Yeah. So it's so frustrating. So  that it's it's a great tool for transferring the
5:48:28
files because it's so easy. But once it's on the  computer where you want to use it, get it out of there so that it will stay there and not disappear  and pretend to be there but not actually be there.
5:48:40
Peer-to-peer file sharing on the macOS is the  way to go for this, right? Go to the network,
5:48:49
connect to Vox, you know, Voxel Mac  Studio. Here's the production folder.
5:48:55
There's the desktop. There's the QClass  Stream Mixer. Here are the assets. I drop more
5:49:02
assets in. They go onto that computer. And  then when I'm collaborating to that computer, they appear as sharable.  That's that's really the way
5:49:14
in the future. I agree that it would be nice to  build a file copy tool into QLab so that anyone
5:49:20
could drop a target on and what it would  do is just send it off to the primary but
5:49:26
that's not easy to do really really well. So,  we have waited to do it until we can devote the
5:49:33
time to it and until we have customers who  say like, "Yes, this is a thing we really want cuz it's it can be really it can really  be a bummer to put a lot of time and energy
5:49:42
into a feature that turns out not to be very  useful to people." And then they're like, "Oh, that's great, but I don't use that." So, it can  be like, "Okay, well, we'll build collaboration.
5:49:52
We'll build it the best that we can at to start  and then wait and see what it is that people wish
5:49:58
it do wish it did on top of what it does and  then the ones the the the requests that we get
5:50:04
a lot of that's what we'll do next. So, this is  my opportunity to remind you all that the squeaky
5:50:11
wheel gets the grease. And if you've got a thing  you wish QLab did, the more people let us know,
5:50:18
the easier it is for us to justify spending time  and energy developing that thing. We have a to-do
5:50:25
list that's like 3500 items long, and prioritizing  that to-do list can be a paralyzing challenge. So,
5:50:33
let us know. Let us know what it is that  you really need. And that will help us guide
5:50:39
ourselves. There's only six folks making QLab and  so that we can do it maximum six things at once.
5:50:49
Okay, great. Any well done somebody. Oh  boy. Somewhere George Orwell is laughing
5:51:01
at us and crying. Um okay friends, what  else about collaboration? I will say I'm
5:51:08
sad that I didn't get to see what they  were going to make because usually that's my favorite part of the class up here.  Yeah. You want me to turn it on? I mean,
5:51:18
I don't want to I don't want to I don't want  to derail you from teaching, but Excellent.
5:51:29
Um Um What other questions?  What other questions if any?
5:51:39
Yeah, there's one person at the bottom  of the list who you're quietly cyber bullying and not giving permission to even  do anything. Oh, that's so rude. I'm sorry.
5:51:52
Apologies, Sea Star from LA.
5:51:58
That was that was unintentional.
5:52:03
Um, yes, that's collaboration. All right. Um, if  folks are ready, if folks want to keep playing
5:52:12
around here, that's fine. We can spend some  just playing around time and maybe you will
5:52:18
derive questions. But, uh, if folks if no one  says that that's what they want to do next,
5:52:24
I plan to move on to workflow tools. Okay, great.  So if I put the if I put QLab into show mode,
5:52:34
suddenly none of you can do anything anymore,  but neither can I. So I go out of show mode.
5:52:40
I go to workspace settings and I turn off allow  collaboration connections and poof disconnected.
Workflow tools - find
5:53:02
Okay, there are series of tools built into QLab,  none of which feels like a headline feature,
5:53:11
but taken together, they really sort of make QLab  what it is for me. Um, a lot of these things I
5:53:19
find when I teach them, people are like, "Yeah,  yeah, yeah, yeah, yeah." and then I do one and they're like that that's my guy. So this may be  that for you. I just want to talk about sort of
5:53:29
all of these little workflow tools one at a time  so that you understand what they are and where to get them and maybe you will find them useful. The  first one is find. Find in QLab is one of the tools
5:53:40
that appears in place of the toolbar when you  invoke it. I'm going to use keyboard shortcut. Oh,
5:53:47
are you back on? Yes. Command F. And when  find is active, QLab lets you search the uh
5:53:57
I've got a list here. Cue names, cue numbers, file  names of audio and video cue targets, cue notes,
5:54:04
the contents of text cues, the contents of  network cues, and the contents of script cues in the current cue list. So I type the letter  W. All the cues that have a W in them light up.
5:54:20
I type O and we now are down to just WO R  K workspace. Six cues found in the current
5:54:30
list. And I can use these buttons to work  my way through those six cues. Or I can hit
5:54:37
this button to select all of those found cues  and then click done to dismiss. defined tool
5:54:47
can be a quick way to, you know, to get towards  a cue. Batch edit is a feature that kind of
Workflow tools - batch edit
5:54:54
doesn't really feel like a feature, but whenever  you have more than one cue selected, the inspector
5:54:59
is doing something slightly tricky, which is it  is showing you only the relevant tabs for the uh
5:55:09
for the totality of all the selected cues. So if I  have two text cues selected, I have every tab that
5:55:18
can be edited for both of those selected cues,  which is everything except the text tab. If I add
5:55:27
a fade cue to my selection, I have only the basics  and triggers tab because only the basics and triggers tab exist in both the text cue and the fade  cue and are editable at once. Right? batch edit is
5:55:43
um uh means that whatever I do, whatever I'm able  to edit down here will be edited on all the cues
5:55:50
that are selected. So if I want to take all of  these cues and change their color, they all change
5:55:58
at once because they are all selected and this  is an editable parameter. Does that make sense?
Workflow tools - load to time
5:56:09
Load to time is a rehearsal tool which  allows us to play a cue or a sequence
5:56:17
of cues from some time other than the  beginning. So here's a piece of music.
5:56:26
We could play it from the top. But if this is  for a scene that we're rehearsing, maybe a bit of
5:56:33
choreographed movement in a scene, and we  want to start 25 seconds in, with that cue selected,
5:56:40
I type command T, which is the shortcut for  load to time. Then I type 25 seconds and hit
5:56:46
enter. And now the cue is loaded 25 seconds in from  the top. When I hit go, it starts at 25 seconds.
5:56:58
I can also use the slider to sort of feel  around and find it. And my personal favorite,
5:57:08
uh, those of us who work in dance get this  one a lot. Folks who work in corporate, I expect get this a lot. Can you give  me the last 30 seconds of that number,
5:57:16
please? So, sure. I command t minus 30  and I load 30 seconds back from the end.
5:57:28
Is there a way to uh just like quickly go back  to like this person can't nail this spin and
5:57:37
they need to go over 48 seconds in the show,  48 seconds into the song. They need that 15
5:57:42
times in a row. I don't want to have to keep  clicking and dragging. Is there a way to like mark that? And here's how I do that. I'd make a  load cue. The load cue targets the audio cue.
5:57:53
In the load cue, I go to the load time tab and  I type 48 seconds and I put that on a hotkey.
5:58:02
And now I hit that hotkey and I load it.
5:58:10
Load cues can also load to negative time and  loading and load to time works in sequences as
5:58:20
well. So, oh boy, I rearranged this in  a way that was really helpful earlier.
5:58:33
When I load to time on this timeline group, I'm scrubbing through everything inside.  Ditto the start first. I'm sorry,
5:58:41
not start verse, and enter because there's  no sequence there. Ditto the start first cue.
5:58:51
And of course, Negative load works as well. Oh,  not. No, it doesn't. Should have.
5:59:05
It's too long. Yeah. Thank you.
5:59:13
Math impaired. Arithmetically impaired individual  up here. 45 seconds is too long for the whole
5:59:21
sequence. Yeah. Um, negative load to time for me  is like the kind of number one unsung hero when I
5:59:32
use it every time someone's like that. How long's  that been in there? Like quite some time actually.
5:59:38
Um, so um, good tool. Big fan. Highly recommend  it. I'm going to remove these flags while I'm
5:59:46
thinking about it. And look, I used batch edit  to do it. I selected four cues and typed F, which is the keyboard shortcut for flag. And now  they are all un-flagged. Makes me very happy.
Workflow tools - paste cue properties
6:00:01
Paste cue properties, which um we nicknamed  fancy paste while we were developing it
6:00:06
and then we couldn't get out of the habit. So  we still call it that. Paste cue properties is
6:00:12
uh a sort of hidden feature of QLab. When  you copy a cue, oops. When you copy a cue,
6:00:20
command C or file, uh, edit menu, copy,  you're secretly copying two things at
6:00:26
once. You're secretly copying three things  at once, I think. One is you're copying text, which is the name of the cue or name and  number and time of the cue because when you
6:00:36
paste it into a text document or a spreadsheet or  a spreadsheet, let's let's do that. That's better.
6:00:45
It's Karen's birthday. Oh, how  nice. Create a spreadsheet. Blank.
6:00:52
Command V. The cue that I copied. Oh, this is  just select one cell. No, that's not right either.
6:01:08
Huh. Numbers is being fussy.
6:01:15
You're expecting it to split it into  column. It usually does or it did last time I tried it. Same. I don't know. I have  uh the cue number, the cue name, the pre-wait,
6:01:26
the post-wait, the follow time, and the continue  mode have are all copied as text and paste-able.
6:01:35
That's one thing you copy. The other thing you  copy is the cue itself because you can then
6:01:40
paste the cue, right? Paste a copy, a duplicate  of the cue. But there's yet another thing that
6:01:45
you copy when you copy a cue and that is all of the  attributes of the cue, which you can then use the
6:01:55
paste cue properties tool on or command shift V.  And when you paste cue properties, you get a list
6:02:03
of all of the parameters of the thing that you  copied and you can paste all or any of those
6:02:09
parameters onto another cube. So if you recall,  I was making fun of the people who get vexed
6:02:17
when they move an object in 3D space in rotation  in um in a video cue and they say, "I want to
6:02:24
know how is it rotated so that I can do it again  on another cue." I say, "Don't worry about it."
6:02:29
copy it and then fancy paste the geometry or  if not the whole geometry just the rotation.
6:02:42
Fancy paste is really appealing when you  have a whole show and then there's some
6:02:48
little quirk that you need to adjust in every  cue and you're sitting there going one one
6:02:53
one right. Or you could just instead  select all refine your selection down
6:03:02
to text cues and then fancy paste  just the rotation. And now Yeah.
6:03:14
Yeah. Oh, you are.
6:03:23
It's not actually in this list.  Well, yeah, let's do that. So, let's take all the cues in this group  and select them and go to the tools menu
Workflow tools - renumber cues
6:03:36
and re number selected cues. This  renumber tool lets you start at a number,
6:03:44
increment by some number,  optionally with a prefix,
6:03:50
and optionally with a suffix.
6:03:57
And now all those cues are renumbered in  increments of 10 with a prefix and a suffix.
6:04:05
Obviously the prefix and the suffix  and the increment are all adjustable. So I could do it with no prefix and no suffix.
6:04:13
Well, yeah. So I just that was command z undo. But you can also quickly delete numbers of  selected cues by choosing command D.
6:04:26
Um I re number a lot when I'm working on show  control. So, when I'm in an environment, uh, Alec,
6:04:33
you were talking about how when you, uh, are in  a show control conversation, you show people the
6:04:39
timeline with the slices on an audio cue and the  letting department's like, "Great, you're the show control boss and we'll listen." When that doesn't  work, the culture of theater uh particularly at
6:04:53
like the higher end of the professional scale of  the theater industry here in the United States
6:04:58
is lighting people have more cache than sound  people. So when they say it's going to be like this and sound people say it's going to be like  that, it's like this. That's just how it is.
6:05:10
And as someone who got yelled at by a multiple  Tony award-winning s lighting designer in front of a whole room of people for doing something  he didn't care for and then apologized to very
6:05:20
quietly privately. Few people feel that more than  I yelled at big apologized to small not cool Mr.
6:05:32
A who I will def identify no other way. So, when  that happens, if the lighting department says,
6:05:40
"We are the show control boss, and you're just  going to have to live with that sound." I say, "Fine." But the lighting console spits out a  cue number with every cue, right? What if I've
6:05:49
already got cues that are already numbered  and already booked with the stage manager, and I don't want to re-number them. I can re-number  my cues by just adding a prefix of something
6:06:03
that makes it not the number the lighting console  thought a period. How about a comma? If all of
6:06:11
my cues are comma number, it won't bother me.  It won't bother my operator. It won't bother
6:06:16
the stage manager, but the lighting computer  will be unable to remote control those cues.
6:06:22
So then I can go back and surgically only  number the cues that do want to be triggered
6:06:27
by the letting computer without a comma. Take  that. This tool is a very powerful thing for me
6:06:42
as is inevitable when I do this particular demo. I lost my background. There we  go. Okay. Recording cue sequence.
Workflow tools - record cue sequence
6:06:53
The cue sequence recorder was created um  by my colleague Christopher here uh in
6:06:59
a moment of impatience with not having  it. Is that fair? Yeah. Um this tool
6:07:08
um lets you perform a series of goes and have  QLab watch and learn. So, I'm going to uh do a
6:07:20
little demo for that. Um, here I have a  group of thunderstorm parts. Of course,
6:07:28
I do. I'm going to go to the tools menu and  choose record cue sequence. And the cue sequence
6:07:34
recorder is going to live here on my screen.  And it's going to make a timeline group cue.
6:07:43
When I click start recording, it's  going to start watching for my first go,
6:07:53
the cues going to go, but also the cue sequence  recorder is going to take note of when I hit go.
6:08:02
And now maybe I'm watching a rehearsal.  Good time for thunder. Maybe then is
6:08:08
when the person enters and says the dramatic line.
6:08:14
It also helps me not think about how I'm  just going to type in numbers of pre-weights.
6:08:23
Maybe that's it. Maybe that's enough thunderstorm.  When I hit stop recording, QLab makes me a group cue.
6:08:33
And that group cue, the recorded sequence of seven  cues, is a series of start cues which start the cues
6:08:39
that I started. And the pre-wait times are all  times relative to when I started recording with
6:08:48
the first go. So when I hit go on this group,  I get the exact timing that I performed while
6:08:55
the cue sequence recorder was recording. Maybe it's  not going to produce exactly the sequence that
6:09:03
you need for a show. I found that this  is supremely useful in two conditions.
6:09:09
The first one is when there's a series of events  on stage that are precisely choreographed that I
6:09:15
want to follow along with and I don't either have  the time or ability to videotape a rehearsal and
6:09:20
then meticulously watch through the tape and  make it happen or when I'm trying to feel out
6:09:26
something organic responding to a performance and  I don't really know what it's going to be so I
6:09:32
can just turn that on and sort of react. Really  like this tool. I use it a lot. questions here.
6:09:42
The other thing I like about it is that there's  very seldom questions about it because there's really not a lot to misunderstand. It just  sort of does what it says on the tin. And
6:09:51
um I'm a big fan. Okay, the workspace  status window. We've been working our
Workflow tools - the Workspace Status window
6:09:58
way through the workspace status window bit  by bit throughout the class. We looked at
6:10:03
the warnings tab. We talked about where  broken cues and warnings appear here,
6:10:09
but we didn't really dive in because there's a  bunch of different symbols that appear. And the idea with these symbols is that they're meant  to show you the different types of warnings.
6:10:22
The caution triangle within ellipsis is what  we call a non-breaking warning. This means
6:10:29
something's not right, but QLab can't determine  if that's a showstopper for you or not. Siphon
6:10:35
root has no clients is a prime example. I have  a siphon server set up in this workspace which I
6:10:44
used to demo the siphon recorder app or whatever  but I'm not using it all the time. QLab noticed
6:10:52
that it doesn't have any siphon device receiving  and wants me to know that. But that might not be a
6:10:59
problem for me and in fact it is not a problem for  me. So I can ignore that warning. A circle with an X means a disconnection. So we have a camera  patch that's not working because the input device
6:11:13
is missing. It has become disconnected. Recall  I was using the camera on my laptop yesterday over NDI. This cue this instance of QLab this copy  of QLab of course is aware that that copy of QLab
6:11:26
is no longer running because it's not sending  video to it. So there's been a disconnection. So the input device is missing. And when I  unfold that uh warning, I see that it causes
6:11:37
another warning which is a broken cue which is this  camera cue. This camera cue uses this input patch.
6:11:44
Since the input patch is not functional, the cue  is not functional. Does that make sense? Great.
6:11:55
A workspace warning with an exclamation  mark is like a broken cue but for settings.
6:12:03
So we have a video output stage  that's missing. All these text cues
6:12:13
are assigned to an invalid stage.
6:12:18
Whenever I select any warning in this list, I  have two buttons down below. The one on the right,
6:12:28
if your computer is online, opens a web browser  to the page of the documentation that is most
6:12:35
likely to be pertinent to the problem that  you've got selected. It's not perfect every
6:12:41
single time. Sometimes because basically this is  just I took a guess. I thought which part of the
6:12:49
documentation was most likely to help a person  who's having this problem and I filled in that
6:12:55
link. It might be that it won't help you the most  and there's another page of the doc that would
6:13:00
help you more and if you find that to be true and  I'd love to hear about it, but it's my best guess.
6:13:06
That's this button. The button on the left changes  based on the type of warning you've got selected.
6:13:12
If you've got a settings related warning  selected, the button will open that pertinent
6:13:18
part of settings so you can jump right to the area  where the problem is and deal with it. If you've
6:13:24
got a cue selected, the button will select that  cue and show the inspector in the appropriate
6:13:31
tab so that you can jump right to that spot and  solve the problem. So you can use the warnings
6:13:37
tab as a punch list for working your way through  your problems. would that it were so simple for
6:13:44
problems outside of QLab. Yeah. Okay, great. If you  want to hide an individual warning from this list,
6:13:54
Yeah. Yeah. Yeah. I know it has no clients and  I don't care. You can check the hide check box and it will vanish. There are 23 warnings. One of  them's hidden. Then you can get through all of the
6:14:04
things. Oh, note. Note, note note. Inspect  that cue. Un-flag it. Now it's out of the
6:14:11
list. Then you can work your way all through  and have only hidden warnings and then say, "All right, I have only hidden warnings. What  are they?" Show hidden rows. Oh, yeah. You okay,
6:14:20
I can deal with you or not. Hiding is just a way  to make it clean it up visually for you. Yeah.
6:14:28
The logs tab of the uh workspace status window  lets you log cue triggers, MIDI input, OSC input,
6:14:37
and OSC output for troubleshooting purposes.  So, if I've turned on MIDI input, and I start
6:14:44
hitting go on my button here, it shows me what's  happening. I'm getting a note on on channel 8.
6:14:53
Note number 13, velocity 127 when I press the  button, velocity zero when I release the button.
6:15:02
And because I've got this cue list active with the  play head nowhere, this go is not doing anything.
6:15:11
But if I hit other buttons on my device,
6:15:17
I see those other messages. Yeah.
6:15:30
cue triggers lets me see any reason a cue  might be triggered, whether it's a hotkey
6:15:39
or Y. OSC input and output likewise shows OSC  messages coming in and OC messages going out.
6:15:49
Something that's new in QLab 5.5 is that there is  a filter here which lets you sort through what's
6:15:56
um in the list. So if you've got a massive wall  of text here, you can just search for hotkey and
6:16:02
it will only show you hotkeys. Also, the state of  these checkboxes is saved with the workspace. So
6:16:09
if you're trying to do some kind of cue triggering  logging and you save and quit and reopen QLab, it will stay the box will stay checked.  Please hear me. Anyone heard of Heisenberg?
6:16:23
Uh you cannot log things without having a  performance effect on your computer. What we hope
6:16:30
is the performance effect is very small but it is  not zero. So, I encourage you to turn off logging
6:16:38
if you don't know that you need it. Because if  you have a performance problem while logging,
6:16:44
it is conceivable that the logging of the  performance problem is part of what's causing the performance problem. Heisenberg and Schrodinger were  driving in a car. Cop pulls them over and says,
6:16:54
"Do you have any idea how fast you were  going?" And Heisenberg says, "No, but we know exactly where we are." Cop says, "Will you mind  popping the trunk?" And so they do. and he says,
6:17:03
"Do you realize you have a dead cat in here?"  And Schrodinger says, "Well, NOW we do." Some
6:17:09
people do not find that funny. That's the logs  tab. The triggers tab we already talked about.
6:17:17
It lets you view a complete list of all the  triggers, time code triggers, hotkey triggers,
6:17:24
but also all of the workspace triggers, which are  the MIDI messages and um uh keyboard shortcuts in
6:17:32
this tab. The MIDI messages in this tab and the  keyboard messages in this tab. You can find them.
6:17:37
If you see the one you want to deal with, you  hit edit and it jumps you right to that one.
6:17:45
The Art-net tab we already talked about. It lists  Art-net nodes on your network which respond to the
6:17:52
uh the hey, how are you message which  the name of which just left my head.
6:18:02
The video metrics tab is a subtle creature.
6:18:08
The video metrics tab shows you um two rows of  information for every stage that is currently
6:18:19
being output. Is that true? Every stage or every  route. Chad wrote this part. Chad wrote this
6:18:24
part. Anytime you're sending video from QLab, you  see information here. It must be routes. Yeah.
6:18:39
Yeah. So, here we go. The output renderer for the  DeckLink device that is sending video. DeckLink is
6:18:47
um uh Blackmagic's name for their video devices.  The output renderer for the DeckLink device here.
6:18:54
The output renderer for the siphon device.  The output renderer for the NDI device.
6:19:00
And then we also have file players and stage  renderers. So, there's a lot going on here. This is all of the steps for creating video  output. And each step gets its own log. Is it
6:19:12
an output? Is it a stage? Or is it a source?  A source is like a cue. It shows the frames
6:19:18
per second of that device and its target frame  rate and it shows the amount of time it took to
6:19:25
render one frame of video on that output.  So looking at this stage renderer line,
6:19:33
the target output is 60 frames per second.  And we see that most of the time it's
6:19:38
running just about exactly at 60. Sometimes  a little slower, sometimes a little faster,
6:19:44
but the render time that it took to render  one frame was 2 point something milliseconds, which is just over 12% of the total am allowable  time to render one frame. If you have one frame
6:19:59
ready, you display that frame. How long do you  have to render the next frame? One frame worth
6:20:06
of time. A 60th of a second in this case. If the  target frame rate and render time fall to within
6:20:15
n fall to 90% of optimal, it'll turn orange.  If it falls to 80% of optimal, it'll turn red.
6:20:25
This will help you decipher video problems if  you're having video problems that are visible.
6:20:34
Logging impacts performance. So if you're not  having video problems, don't come looking here
6:20:40
because you will cause video problems. You won't.  You might. That's the video metrics tab. The info
6:20:47
tab shows the workspace ID for the workspace and  the machine ID for this Mac and has a copy button
6:20:53
so you can copy it and paste it into an email  to us when we write to you when you write to us with a problem when we respond. Would you please  send us the machine ID or the workspace ID? That's
6:21:03
pretty much the only reason you need to do this.  Though sometimes if you're doing certain clever kinds of scripting, you might need to know one  or the other. That's the workspace status window.
Workflow tools - media logging
6:21:25
Media logging is a feature that um is one of  those things that means a lot to some people
6:21:30
and means nothing to others. Under the QLab  menu in QLab preferences in the general tab,
6:21:36
if you check log media playback, QLab will log  the playback of any audio or video files to a
6:21:44
spreadsheet and we'll save that spreadsheet in  the workspace folder. So, let's see if I can.
6:21:55
I've turned that on.
6:22:00
Yeah. And here's my log on 9525. That's today at  3:140 p.m. which was just now a cue called load
6:22:10
to time example plus and minus started playing. It  doesn't have a cue number. The path to the file is
6:22:16
users production desktop QS5 audio moonlight.if.  The playback duration was 7 seconds and we started
6:22:22
at 0 seconds in the file. Was it rate adjusted?  No, it was not. And then here is the metadata
6:22:29
inside the MP4 file that I played. If it has it,  it'll show it. The title is Moonlight. The artist
6:22:36
is Sam Cousins and Luke Norby. The album is Lucky  Luke's Legacy Archive. There was no copyright date. There was no publisher date. And that's  a piece of music that Luke and I recorded for
6:22:45
a podcast that we did together. I'm using music  that I wrote in this class so that YouTube doesn't
6:22:52
take our stream offline for using copyrighted  material. I own the copyright to this YouTube.
6:23:00
So that metadata isn't here. If you're working  working in radio and you're using QLab for playback, this document is what you need to  send to your producer so that your producer
6:23:09
can send the document they need to send to  BMI and ASCAP to make sure that you've done the right thing with royalty payments and  rights agreements and so forth. If you are
6:23:20
not someone in that context, it's probably not  that useful to you. Although you never know.
6:23:32
Darn it. Now, the pop popping out the inspector.  All this while we've been talking about the
Workflow tools - pop-out inspector
6:23:40
inspector down here at the bottom of the window.  It's been helpful to us. It's been our friend. But it doesn't have to stay here. When I click  this button, it pops out into its own window.
6:23:59
If you have a timeline group and you  want the inspector to be very tall,
6:24:07
this is the easiest way to do it. Or if you have  an audio cue and you plan to do some elaborate
6:24:16
object audio business with it, it could be  convenient to have the inspector popped out
6:24:21
here on your own. I have a suspicion. Object  audio is fairly new to QLab. It came out very
6:24:27
recently. I haven't yet done a commercial  show with it. I have a suspicion that I'm
6:24:32
going to want to start using two monitors on  my desk. one for my workspace and one for my
6:24:39
popped out inspector so that I can do really ex  exact control. I'm not sure that that's true,
6:24:44
but I'm gonna find out this autumn. The popped  out inspector will still behave like the regular
6:24:52
inspector, which is to say whatever cue or cues  are selected, that's what the inspector shows.
Workflow tools - secondary inspectors
6:24:59
But another inspector was made. You can at any  time select a cue, right click on that cue
6:25:10
and choose open in new inspector window or  you can from the regular inspector hit the
6:25:19
clone button or you can go to the window menu and  choose is that true? Is that not true? Not true.
6:25:35
Yeah, I just Yeah, that's the  view menu. In the view menu, view inspector for selected cue. Yeah.  And all of these things will give you a
6:25:44
secondary inspector window. Somewhat  alike in dignity, but not identical.
6:25:53
The secondary inspector window stays  locked to the cue that it was opened for,
6:25:59
although there's a menu in its footer that  lets you choose any cue in your workspace.
6:26:06
And you can inspect that cue. Yeah, this is a  great way to compare two cues to each other or
6:26:14
look at two different parameters, two different  tabs of the same cue at once. And you can make
6:26:20
as many inspector secondary inspectors  as you want. It is confusing if you let
6:26:26
it be confusing. The way to tell the popped out  primary inspector from the secondary inspector,
6:26:32
the primary inspector will change whenever  your selection changes. The primary inspector tells you how many selected cues  there are in the lower left corner,
6:26:41
whereas the popped out inspe... I'm sorry,  the secondary inspector has a menu. The primary inspector has a pop me back in  button. The secondary inspector does not.
6:26:59
We've already talked about cue colors  and secondary cue colors in detail, so I'm not going to continue with that.  We've already talked about cue templates,
6:27:08
so I'm not going to talk about that. What I  promised we'd talk about workspace templates.
Workflow tools - workspace templates
6:27:18
I'm going to save this workspace and close it.
6:27:26
And I'm going to make a new workspace. And  in this new workspace, I'm going to make some
6:27:33
choices. In workspace settings, templates,  I'm going to say that my default new group
6:27:39
mode should be playlist group. I'm going to  say that all new audio cues should be orange.
6:27:46
I'm going to say that all new mic  cues should use um should use an
6:27:53
unpatched audio output because I am anxious  about accidentally having them run wrong.
6:28:02
And I'm going to start with two memo  cues. The first one says a new show.
6:28:10
And the second one says from the Voxel.
6:28:17
And those won't have numbers. And now I'm going to go to the file  menu and choose save as template.
6:28:37
And when I choose save here and close this  workspace and not save it, I am now able to
6:28:46
go to the QLab to QLab's file menu and choose  new from template and either make a new blank
6:28:53
workspace which is the default behavior or make  a new workspace based on Voxel class template.
6:28:59
that new workspace comes into being exactly  in the state that the other workspace was in
6:29:06
when I saved it. So, new mic cues start off with  their output uh their input unpatched. New mic
6:29:17
uh new audio cues start off orange and  new group cues start off in playlist mode. Those were the settings that I chose.  If I had reordered my cues in the toolbox,
6:29:28
they would be reordered in this template.  Anything I do, including target media, if it's available on the same computer, anything I  do and save in the template, saves along with. So,
6:29:40
a cue template can be a really, really useful  way to have a common starting point. All my
6:29:45
clever scripts are in my cue template. That way,  I don't have to copy and paste them every time.
6:29:56
questions about this.
6:30:03
If you want, you can go to workspace templates,  manage templates, and set your template as the
6:30:10
default so that command n uh new workspace uses  your template. Or you can manage templates and
6:30:20
delete or rename the template. Yeah. Is there a  place to find that in Finder? If you right click,
6:30:26
you can choose reveal and finder. And there it  is in library application support QLab templates.
Workflow tools - settings import/export
6:30:36
We've talked about settings import and export,  but just to drive it home. In the workspace
6:30:42
settings window, you can export some or all  of your settings to a settings file. And you
6:30:49
can import settings either from a settings file,  from another open workspace, or from QLab defaults.
6:30:58
We haven't talked about the launcher  window yet or file management, but I'm going to propose that we take a quick  break and come back to them with fresh eyes
6:31:07
because I'm starting to feel that we've just been  in like lecture mode for quite long enough. So,
6:31:12
let's take a few minutes uh use the  restroom, you have water, stretch legs, whatever it is. Then we'll come back and  finish up this topic and then where do
6:31:21
we go next? Only you can decide. I hear  people want to play with collaboration.
Break
6:31:30
I'm ready to take a break. If you
6:43:49
All right, folks. Welcome back. I  hope that your break was restful.
Workflow tools - the launcher window
6:43:56
um two more workflow tools uh and then we  get back to a more open question although
6:44:03
there are a couple of topics that have  come up which I think we may pursue. Uh,
6:44:09
okay. Workflow tools, launcher  window. The launcher window.
6:44:15
This window appears by default when you launch QLab  and it's sort of a a starting point. Um, under
6:44:22
the recent workspaces tab, you see all the recent  workspaces up to a limit of I think 10. Um, under
6:44:29
the templates tab, you see all of the workspace  templates that you have on your Mac. And on the
6:44:37
left there are a couple of useful tools. There's  a just a big open button, a new button, a connect
6:44:42
button for connecting to remote workspaces, a  shortcut for opening the license manager window,
6:44:49
a link to check for updates, a link to the  documentation, a link to the tutorial section of the documentation, and a link to our customer  support uh communication. Um, check for updates
6:45:02
will change color when an update's available. Um,  so that's a place to peek. Um, you also go here
6:45:10
to check for updates. And in QLab preferences,  you can ask, is it in QLab preferences? Where
6:45:24
do I tell it to please automatically or not  check? Yeah, I think it was in that window.
6:45:32
Oh, right here. prompt automatically prompt  about updates or not right here. Thank you.
6:45:39
The launcher window will show by default,  but if you don't like the launcher window for whatever reason, you don't want it to  appear when you launch QLab in QLab preferences,
6:45:47
you can tell it what to do at launch. Should  I show the launcher window? Should it restore the most recently opened workspaces? Should it  create a new workspace from the default template?
6:45:55
Should it create a new truly blank workspace? Or  should QLab just do nothing when it opens but open.
6:46:04
And that's the launcher window. Folks have  asked how to clear recent workspaces here.
6:46:10
And the answer is this is the same recent list as  this recent list. So when you go to recent items,
6:46:19
clear menu, that will clear this list as well.
6:46:27
Yes.
Workflow tools - file management - file targets, autosaving, and backups
6:46:33
Okay, now I want to talk about everyone's  favorite and most exciting topic, file management.
6:46:40
Okay, in the beginning there were no files and it  was great. Um, but then we invented files. Um, no,
6:46:49
in uh QLab there were two ducks and one  file. Two ducks in one file. And yeah,
6:46:54
and the two ducks said, "Well, where you  going to keep it?" Over there. Over there. And then they had to invent computers.  That's in fact exactly how the myth goes.
6:47:09
The two ducks meet the coyote and  then they find land under the water. It's a really beautiful creation  myth. Highly recommended. Okay.
6:47:21
In QLab prior to five, when you brought when  you created a cue that targeted a file,
6:47:29
like an audio cue that targeted an audio file  or a video cue which targeted a video file or a MIDI file cue which targeted a MIDI file, if you planned  to move that workspace to another computer, a
6:47:40
challenge was born. How to make sure all the media  comes with. We had a thing called bundling where
6:47:48
it would make a copy of the workspace, make a copy  of all the media and copy it all together into a folder. You could move that. But bundling caused  some subtle problems for some folks. And the
6:48:00
aforementioned UU ID clash where sometimes moving  files to a new computer would cause it to give it
6:48:05
a new UU ID could further complicate the issue.  So in QLab 5, we took a different approach which a
6:48:14
very small number of people found vexing out loud  anyway. Um but most folks seems to find un-vexing
6:48:22
and I'm certainly one of those folks. And this is  how it works. When you go to workspace settings,
6:48:30
general file management, you are faced with these  checkboxes. And by default for new workspaces,
6:48:37
all four boxes are checked. And I'm here to  encourage you to really think for a moment
6:48:43
before unchecking these boxes about what it will  do. But you're in this class, so you don't have
6:48:49
to think for a moment because I'm going to  tell you all about it. The first checkbox,
6:48:54
copy files into project folder when adding  to workspace. This is kind of the big deal.
6:49:03
This folder QClass 5 is my project folder.  This Wonka folder is the project folder for
6:49:10
a QLab workspace called Wonka. Here's the project.  Well, no, never mind. That's not true. The QClass
6:49:20
project folder has video, audio, fonts, audio  map images, masks, and MIDI files. And fonts
6:49:28
is not with a capital F. Fonts is not one of the  automatically generated folders, but the others are. When I take a piece of media and I target  it in QLab, if that media comes from outside my
6:49:47
project folder, QLab notices, copies the media into  my appropriate folder, and then instead of setting
6:49:58
the target to the file I originally dragged, it  sets the target to the copy that it just made for
6:50:06
So, as long as this checkbox is checked,  this folder contains every file target in
6:50:16
my show. If I go to workspace, settings,  video, stage editor, and set a mask,
6:50:27
if I drop in a mask there, that mask  file gets copied into the media folder.
6:50:32
MIDI files get copied, audio files, video  files, background images for audio maps,
6:50:39
fonts do not automatically get copied because  they are not the subject of targeting. I put that folder there because I was tired of copying the  QClass workspace folder to a new computer every
6:50:49
year that I came to the Voxel to teach this class  and Alec had a different Mac for me here. I was sick of forgetting to bring the fonts over so I  just put them in here. So that's just a SAM thing.
6:51:00
The automatic targeting of files and copying  into your workspace folder all but eliminates
6:51:08
the consternation surrounding moving a workspace  to a new computer and then wondering where are my
6:51:16
damn files, right? Small drawback is they  all get copied. They never get deleted.
6:51:24
So if you do version after version of your media,  these files are these folders are kind of balloon
6:51:30
in size. That's for you to manage on your own.  QLab doesn't want to delete nothing. Let you
6:51:36
delete things. It's your stuff. You delete it. You  can, if you wish, save as. And when you save as,
6:51:56
your options include save only the workspace  file or save the workspace file and media to
6:52:01
a new project folder or customize your  settings. Customized settings right now
6:52:07
doesn't make a huge difference because the only  settings are should I or should I not do that.
6:52:15
But we made it this way because we expect that in  the future there may be more settings to customize
6:52:21
and we don't want to reinvent that wheel in the  future. Yeah, I know how much you love ProTools,
6:52:29
but ProTools has a feature in it where you can  select unused media and remove stuff like is there
6:52:37
any kind of function like that in QLab to help not  quickly delete stuff that's not in your workspace?
6:52:44
Not built in. You can save workspace and media  to a new project folder. And when you do that, it will only save the targeted media. So saving a  saving as will make a copy that's slimmed down to
6:52:57
only the use the useful stuff. Okay, that's but  um I once wrote a script that was like go through
6:53:04
all your stuff and highlight the files in the  finder that aren't used. And I was like it works, but it's kind of clunky. It seems plausible that  we could create a thin your media folder. Vector
6:53:17
Works also has a clean things up, right? The  purge, right? Of course, with Vector Works,
6:53:23
the inevitability is some of the things that  you're purging are things you've never heard of. How did they get here? Did I put them here?  Did you put them here? Vector Works is like,
6:53:31
I'm not telling. You want to get rid  of it? Might be really important.
6:53:37
Gosh, I don't know. Vector Works. I really  don't know. Can you help me? I could help you, but I won't. And I'm going to charge you  more now. And I'm going to charge you more
6:53:47
now. Yeah. Has anyone here a Vector Works  Service Select subscriber? Are they trying to hawk their subscription? Yeah. Let's find  out what will I actually pay this year. Oh,
6:53:56
no. We can't tell you that. I just  reacted. I'm like, okay. Yeah, it's
6:54:04
really soon they're going to discover that the  theater industry is done with their nonsense. The trouble is the theater industry probably  represents an a literally invisible amount of
6:54:14
their income. The other trouble is no one else's  tool comes close to the functionality of Vector
6:54:20
Works. There are people out there who disagree  with me on this. I'm happy for them and I don't
6:54:25
think their paperwork looks that good. So, I just  can't like I this is the one that does it and they
6:54:33
don't care about us but we need them. It's really  frustrating. I'm sorry. They got a monopoly.
6:54:38
They've got a monopoly. Not not for scenic  folks. You you scenic folks, you use AutoCAD and I'm very impressed with you. But you can't do  what I do with signal flow diagrams in AutoCAD.
6:54:49
Not without, you know, shortening your lifespan.  Um, so stay stay good Vector Works over here away
6:55:00
from me right now. So let's close these windows  that I opened up in enthusiasm and return to file
6:55:07
management. Okay, so let's copy files. Big  thumbs up. Really, really encouraged. Next,
6:55:13
automatically make backup copies of this  workspace. We've all been there. QQQ.
6:55:19
Program program design. Everything looks great.  This is the best show I've ever done. Crash.
6:55:27
I have a kind of nervous tick. Commands behavior  in my left hand. Um, which has been built up
6:55:34
from being bitten over the many, many years  because I've been using a Mac since the very early 1990s. Right? So for me that habit has  been built in many different programs caused
6:55:44
by many different crashes over several decades  in different contexts. But now QLab automatically
6:55:52
will make backup copies for you. If you go to  the QLab menu to QLab preferences and look here,
6:55:58
no look here. This is the autosave interval. It  can be as low as five seconds and it can be as
6:56:08
high as 600 seconds. Every autosave  interval seconds, in this case 30,
6:56:16
if you are not in the middle of typing and if  you are not in show mode, QLab will make a copy
6:56:24
of your workspace as it looks right now. If this  second checkbox is also checked, make backup copy
6:56:32
when saving before saving, QLab will also make a  backup copy according to a scheme that actually
6:56:41
makes good sense, but takes a moment to explain  clearly. It's 9:00 a.m. I open my workspace.
6:56:51
The red button does not have a little dot because  I just opened it and nothing has changed. So,
6:56:57
it's un dirtied. It's clean. That's 9:00 a.m.  Between 9 and 10, I work work work. Design
6:57:06
design. At 10:00 a.m., I hit command S to save. If  this checkbox, this one is checked, QLab makes an
6:57:20
autosave copy of my workspace as it looked at 9:00  a.m., then lets me save regardless of the other
6:57:29
automatic backups. Forget those. What if this is  unchecked? If that is unchecked, then no backups
6:57:35
were getting made during that hour and I was life  on the edge, right? Then I hit command S and QLab
6:57:42
because of this checkbox makes a copy exactly as  the workspace looked at 9:00 am and then saves.
6:57:48
Then I work work work till 11:00 a.m. and then  I hit command S and QLab makes a 10:00 a.m. copy
6:57:55
and then saves. And so what this does is allow me  to stamp in time certain changes. And rather than
6:58:07
certain changes, what I'm really stamping in time  is I'm going to say save everything I did after
6:58:12
that. Maybe I'm going to throw that out. Maybe  I want to get back to what it looked like at 9. Maybe I want to get back to what it looked like  at 10. So you can dig through your backup folder
6:58:22
and find the one that was stamped right at 10:00  a.m. Be like, "Yeah, that's my guy. If everything I did since 10 a.m. was hogwash, I can go back  to my 10 a.m. version." That's that box. Okay.
6:58:35
Now with these two boxes combined, this box comes  into play. Rotate backups. With the rotate backups
6:58:44
box checked, QLab will routinely delete old backups  to prevent using up too much disk space. No matter
6:58:56
how the backup was made, whether by this checkbox  or that, QLab with this box checked will keep the
6:59:02
20 most recent backups within the last hour, the  latest backup in each hour before that for the
6:59:11
last day, and the last backup per day reaching  back to the beginning of time. So, I work on
6:59:21
my show. I work on my show. Saving, saving,  saving. Backups, backups, backups for the It's
6:59:28
352. Between now and 252, I've got the 20 most  recent backups. Then at 252, I'll find a backup
6:59:38
from approximately 252. I'll also find a backup  from approximately 152 based on exactly what was
6:59:44
going on at the time. Roughly 1 hour intervals all  the way back to the end of the day. Then I'll look
6:59:52
in my backups folder and I'll see that the very  last backup made yesterday is preserved, but all
6:59:57
the other backups yesterday are gone. Then all the  backups made on Wednesday are gone except for the
7:00:03
last one of the day. And so on all the way back to  the beginning of time for this file. So the amount
7:00:10
of granularity of rescuing myself reduces as I  reach farther back. But also presumably by the
7:00:16
time we've gotten several days along if I need  to reach back in time, I hopefully don't need
7:00:23
to reach back to only before lunch or only after  lunch 8 days ago. Hopefully. And if I did need
7:00:29
that, I could have always saved a copy and stashed  it away somewhere else. Yeah, I've used this a
7:00:36
lot, right? I did a show in which uh one day  during previews the director and the playwright
7:00:44
came in and said we're going to swap scene two  and scene six and we were like I'm so sorry what
7:00:51
in a nine scene play we're swapping two and six  and they're like trust me and actually it was a
7:00:56
brilliant edit and it totally super worked but I  was freaking out like what are we going to do in
7:01:02
the QLab file so I made a whole other QLab you know I  made a lot of changes then after two previews are
7:01:08
like, "No, we're going back. Nice idea, but we're  going back." If it had been during the lifetime of
7:01:13
QLab 5 that I'd done this show, I could simply look  through my backup history and find the last backup
7:01:19
before we made the change and I would have had a  perfect restoration of what QLab had looked like.
7:01:26
As happens, I because I was anxious about it saved  it to a flash drive and put it in another room and
7:01:32
was like in case of emergency, break glass,  retrieve flash drive, do new version of show.
7:01:39
Are there questions about this? This button lets  you quickly jump to the backups folder for the
7:01:47
current workspace file. And it also shows you how  much disk space it's taking up right now. And then
7:01:54
here are all the backups. And they're named kind  of humanely. The name of your show and then backup
7:02:00
date underscore time. The ISO standard for writing  dates. Year, month, day, underscore, hour, minute.
7:02:12
Yeah. I cannot emphasize enough how much I encourage  you to leave all these boxes checked. Did I
7:02:22
mention that I think you should check these boxes?  Automatic backups are just like free money in your
7:02:31
pocket because time is money and you don't want  to spend time reinventing your workspace when your
7:02:36
computer something you know someone I was before  the days of Mags Safe I was teching a show and
7:02:42
the director walked past my tech table, tripped  over the power cord of my laptop, flung the laptop off the desk and cracked what turned out to be the  little daughter card that had the power connector,
7:02:54
the headphone jack, and the mic jack all on one  little card on the side of that model of laptop
7:02:59
just severed that circuit board in half and so  like okay well there's no theater happening until
7:03:07
I get that fixed like that was a very upsetting  feeling have fall I'm sorry did a tear fall a
7:03:13
tear she fell it was not a nice day it was a  sad day and it was a sad $350 repair which for
7:03:20
like a college junior was like a lot of money  I mean it's a lot of money $350 is a lot money,
7:03:26
but I was a junior in college and I  was very pouty about it. He threw in uh the cash. Um but in QLab land, well, my laptop  would have been in trouble, but the backup saved
7:03:39
could have been put onto another Mac and but the  power cable got unplugged. So, it was actually a
7:03:44
double whammy. I lost all the work that I'd  been doing and the Mac had to get replaced, I mean repaired. So, these check boxes, these  check boxes are your friends. And yeah, the
7:03:54
disc will fill up and you know that's what it's  for. That's why you have a disc, fill it up. Um
7:04:02
the end. Okay.
7:04:08
Yeah. You you can't you can't what what are  you going to do with an empty disc? Less. Okay.
Auditioning
7:04:22
Auditioning. We talked about this very quickly  yesterday at Alex wise urging, but I want to
7:04:27
talk about it in a little bit greater detail  because QLab 5's audition feature is different from QLab 4 and better and takes a little bit of  getting used to. An audition is a performance,
7:04:40
but that's not the show, right? That's what it  really is. When you audition to be in a show, you walk in and perform for the director or the  casting director, but it's not really the show.
7:04:49
So, QLab has a feature called audition. Um, I once  worked with a director who had this little quirk.
7:04:56
If I played a sound cue at wildly too loud  volume by accident, no force on earth could
7:05:04
compel her to like that sound cue ever again.  So, if it was the perfect cue for the scene,
7:05:09
but it was accidentally too loud, she said, "No,  cut that." And if I tried to sneak it in later
7:05:16
on at a reasonable level, she said, "I said cut  that." and that really made it very difficult for
7:05:21
me to enjoy working with her. So, auditioning is  your tool to protect against that. When you have
7:05:32
uh that's not actually going to be a great  Oops. Undo you. Goodbye. You come here.
7:05:40
When you have a cue in QLab, there's two ways  fundamentally to play it. You can run the cue
7:05:50
Or you can audition the cue. When you audition  the cue, the cue plays through the audition
7:05:57
output. And what is the audition output? So  glad you asked. In workspace settings, audition,
7:06:06
there is a table showing the different sorts of  output that QLab can produce. audio, video, MIDI,
7:06:15
MTC time code, LTC time code, network messages,  lighting output, and the behavior of cues which
7:06:23
target patches, which is sort of fundamentally  different than the behavior of cues which target other cues or media. The audition output is  a patch that you choose which will be used by
7:06:37
any cue that's auditioning. So in the IO tab, this  sound cue is playing audio cue is playing to the main
7:06:46
audio patch. But if I audition this cue, which the  default keyboard shortcut for is option spacebar,
7:06:56
it plays through my audition patch, which  is the built-in speaker on this Mac.
7:07:03
Enough to tell it's working. I have a little  um Fostex 3-inch speaker, powered speaker with
7:07:13
a Dante input built into it. It lives on my desk,  uh my tech table. I have a patch that routes all
7:07:20
of my playback to that speaker. That patch is  my audition patch. If I were working with that
7:07:26
director today and I wanted to try something  out, I would not play it in the sound system. I would play it in the speaker on my desk.  Make sure I like it. Bring the volume way
7:07:35
down. Try it out right when they're not in the  room. Something like that. That's the audition
7:07:42
behavior for audio. But for video, what can I  do? I can send it to a different stage or I can
7:07:48
redirect it to the audition window. And we've  learned about the audition window yesterday.
7:07:56
The audition window is a window  that shows its out that shows the output of the stage as though it were  the actual output, whatever that is.
7:08:09
When you hit regular go on  a cue that's auditioning, it panics and restarts in its real output. So the  workflow can be audition the cue. You like it,
7:08:21
you want to hear it, go hit  it in the real system, right?
7:08:27
Option spacebar is the keyboard shortcut for  Audition go. I've been using and sort of alluding
7:08:34
to the um preview um function. When I hit go on  a cue, it starts and the playhead moves down a
7:08:43
cue, right? But when I hit preview on a cue, which  is letter V, it starts and the playhead doesn't
7:08:51
move. If that cue has an auto-follow or continue,  it is ignored. If the cue has a pre-wait, it is
7:08:57
ignored. Preview is a function for previewing a  cue out of context. Option V is audition preview.
7:09:08
So spacebar is go. Option space bar is audition  go. V is preview. Option V is audition preview.
7:09:23
You can set the behavior for individual types  of output individually, but it's important to
7:09:29
understand that that type of output is regardless  of cue type. So when we say output type audio,
7:09:35
we mean audio generated by audio cues,  mic cues, video cues, camera cues, right?
7:09:42
When we say video, it's video generated by  camera cues, mic cues, video cues. I'm sorry,
7:09:48
camera cues, text cues, video cues, etc.  Light output is generally only generate
7:09:56
is is only generated by light cues. Of  course, network output is generated by
7:10:03
network cues. Time code output is generated by  time code cues. Yes, LTC is technically audio,
7:10:09
but it's a separate kind of audio. So we make  it separate here. Yes, MTC is a kind of MIDI,
7:10:14
but we make it separate. Each type of media has  its own menu with options that are pertinent to
7:10:23
it. So the audio cue out audio output can be set  to leave output unchanged when you audition,
7:10:29
don't audition differently. No output, suppress  it entirely, or pick a patch. Video is leave
7:10:36
it unchanged, no output, sent to the audition  window, or pick a patch. MIDI, leave it unchanged,
7:10:42
no output or pick a patch, so forth. Light  is leave it unchanged, stop any lighting
7:10:49
output when it's auditioned, or redirect to the  audition tab. What's the audition tab, you say?
7:10:59
The audition tab in the light dashboard,  which has this sort of bluish background, looks just like the live tab, except that only  auditioning cues can cause a change here. So,
7:11:12
if you have a light cue that you want to  see what it looks like in the dashboard, you can audition it and you'll see the effects of  that light cue in the dashboard. You can then reset
7:11:23
the audition tab to match the current live state.  And you can make changes in the audition tab and
7:11:30
use record all or update to make new make or edit  cues. So you can use the audition tab just like
7:11:41
blind in an ETC console. You can use the audition  tab to make adjustments that the audience can't
7:11:48
see and update cues which the audience which can  later be run and then the audience can see. Yeah.
7:12:00
And cues which target patches which we  saw with fade cues and reset cues can
7:12:05
be told to either behave normally when  they're auditioned or simply do not run.
7:12:19
If you go to the tools menu, you can turn on  always audition. And when you've turned on always
7:12:26
audition, the go button and the keyboard shortcuts  for go and audition will all turn into audition
7:12:34
goes, I'm sorry, go and preview will all turn into  audition goes and audition previews. Crucially,
7:12:42
if you have a MIDI device that is assigned in  workspace settings, controls workspace MIDI to go,
7:12:51
switching to auto to always audition will not  change that. So, always audition is should is
7:12:58
most technically almost always audition. The  idea with always audition is it's meant to
7:13:05
make your mouse and keyboard work at in on QLab  easier to stay working in audition mode. But
7:13:14
you may while working in always audition have  a panicked moment in which the stage manager is like 12 come on Q12 and you want to be able  to just pick up your MIDI button and hit go.
7:13:24
So crucially, MIDI messages and OSC messages  which say go or preview will remain real go
7:13:33
and real preview even when you're in always  audition mode. Is that logical? Okay, great.
Assorted questions
7:13:49
Uh we talked about licenses.
7:13:55
So now we have entered into a space for the  last just under an hour where where we go next
7:14:01
is really up to you. We haven't talked much about  scripting and I'm happy to dive into that topic,
7:14:09
but I don't want to do it if folks don't  want to do it. You know what I mean, right? If that's not interesting to you,  it will be not interesting to you. Um,
7:14:16
we can talk more about any topic that we've talked  about today. we can play with collaboration more
7:14:23
as I know Chris is really excited to do.  Um I want to go where you want to lead me. So is there any topic that anyone here or  anyone online feels like they are thirsty for
7:14:35
more on that topic or a topic which I haven't  touched yet and you want to hear about. Yes.
7:14:44
But is there a shortcut to close all the  groups? Yes. shift comma or left angle bracket.
7:14:54
So shift period or right angle... shift period  or right angle bracket opens all groups.
7:15:00
Shift comma or close angle bracket  closes all groups. France, Germany, England. I'm not sure what happens for you  all. Um or all of Great Britain actually.
7:15:08
It's not just the English keyboard.  It's the Great Britain keyboard.
7:15:17
Yes. which are also angle brackets. Yeah. But  less than greater than is also the right name
7:15:23
for these things or single quote in Spain  I think. So I have a question and maybe I
7:15:33
mean maybe from a lighting perspective this  is a weird question but like so there was
7:15:39
um opportunity in a lot of the lighting fields  to open up or to do commands just with text like
7:15:45
you were doing a lot of like 11 through 15 at  blah blah blah or you know you were showing oh you can do 11 comma 12 comma 14 comma 17  whatever is that is that like modeled after
7:16:00
like the way ETC does their commands or is  it modeled after like a general way lighting
7:16:07
commands are written on lots of boards? Uh, and  I mean specifically in like the syntax like for
7:16:13
like at or equals or like and then at the end of  the question is is there some document somewhere
7:16:18
for me to learn the specific syntax to be fast  at lighting in QLab and like know all the ways
7:16:24
I can control it just with that text that seems  fast but I don't know the existence of a command line is modeled after our experiences using an etc  console right so I came up on a two scene preset
7:16:38
manual console and then an ETC MicroVision,  which I loved, but the MicroVision had no command
7:16:44
line. The MicroVision was just um was just  an automated two scene preset board almost.
7:16:51
And then the Express, but the first time I sat in  front of an obsession, which was the first command line board I used was the time that was the moment  that I understood that it was possible to leverage
7:17:02
a different set of skills in my brain to work with  lighting quicker. And I don't think this is Yeah,
7:17:12
I think this is absolutely true. An equally  skilled person moving as fast as possible on
7:17:18
an Obsession or an EOS era console can go faster  than on a MicroVision or an Express non-command
7:17:26
line console. The command line allows you to  move faster. And so the existence of a command
7:17:32
line is definitely modeled after the experience  of gosh this feels like an empowering tool. The
7:17:39
exact behavior of the command line in our product  is quite different from the ETC command line. It
7:17:45
works very differently. It has a lot of different  rules. The ETC command syntax is infinitely deeper
7:17:51
than ours. Much much much more complex with a lot  more bells and whistles, a lot more power, a lot
7:17:56
more flexibility, but also a lot more pitfalls.  Sometimes you need to press clear. Sometimes you need to press clear clear. Sometimes you need to  press at. Sometimes you need to press at at. It's
7:18:06
not exactly fully clear to me why, which is what.  There's a lot of like hold down the shift key and
7:18:11
press this button. It does this other thing. And  all of those things are cool, but there's a lot
7:18:16
of them and learning them requires a lot of deep  expertise. Our command syntax is much shallower.
7:18:25
and the lighting command language page  of our documentation is only that long.
7:18:33
So the answer to your question is yes, there is  somewhere you can go and it's here and most of it
7:18:39
we have already covered. I just skipped over  the very basic I skipped over the few things
7:18:45
that feel really edge case-y and not that  important to talk about in a broad sense. The idea of this class is to get you going  to make you feel comfortable and conversant
7:18:55
in every topic, not necessarily to make  sure that you know every every everything about every every everything. There's  something you can do with brackets to
7:19:05
make ad hoc groups. I didn't talk about ad hoc  groups. I guess that's really what I left out.
7:19:12
So, yes, it's here, but I've basically hit  it. Okay. Yeah. Not a lot. Not a lot left. Um,
7:19:20
I am attracted to the question of expanding  upon the lighting command language in QLab. I'm
7:19:27
attracted to the idea of where do we go from here,  right? I think we've got a really great start and
7:19:34
um our um one of the motivating factors was  there was a theater company in town that
7:19:41
um held a big fundraiser to put together the money  to purchase a used express for 4,500 bucks and it
7:19:51
was large and it felt to us that seems like a lot  of money to buy a very definitely outdated piece
7:19:59
of technology. technology that takes up too much  space in your little tiny booth. Maybe we can help
7:20:06
the folks who have needs that are at that level  of lighting sophistication who maybe don't want
7:20:13
a physical... like, the physical size is an impediment  or the price is an impediment or they're already
7:20:18
using QLab anyway or you know all the things we  talked about where letting is is strong in QLab.
7:20:26
uh and then start there and then see where  we go next. So that's kind of that's where
7:20:32
we are. What else? I realize because I  think because the mic pack is in this
7:20:41
pocket that I've been tending this way, I'm  also pointing at the video projectors a lot.
7:20:47
I don't want anyone on this side of the  room to feel in any way neglected. Also, because I know these two individuals, there's a  little bit of like looking at the looking at my
7:20:57
friends. So, I I just don't want you to feel  neglected over here. You're all real great, too. Yeah. What are your some of your favorite  uses for Apple scripting? And how does that
Script cues and scripting QLab
7:21:08
kind of like fit into your work? Anyone here  who's not into this, I'm sorry. Here we go.
7:21:17
This is my collection of Apple scripts  that comes with me to every show. I use them often. I kid you not. I know this is  going to sound funny. It's going to sound like I'm
7:21:28
fishing for a laugh, but as you have seen, I've  been doing that for three days solid. Fishing for
7:21:33
a laugh is not beneath me. But this is not part  of that. My favorite use of AppleScript is making
7:21:38
it so that I don't have to do arithmetic in a  hurry. If anyone here has any form of learning
7:21:46
disability, then you understand that sometimes  your learning disability makes you feel stupid.
7:21:52
But it's not stupid. A learning disability is  a disability. My learning disability has to do
7:21:59
with numbers. And I've got a degree from a fancy  college. I've worked at the top of my personal
7:22:08
game many times. I feel like a professional until  someone who I'm working for says, "All right,
7:22:15
what's the level of that sound cue? What's the level  of that sound cue? What's the level of that sound cue? Can you bump those all down by 3dB?" And suddenly  I feel like a stupid person. And the back of my
7:22:26
head, you know, Sam, you are not a stupid person.  And there's just a thing that other brains can
7:22:31
do that your brain can't do. Well, so I wrote  this script to stop me from feeling stupid.
7:22:39
And it goes like this. Here's three sound cues. This one's at 5.5. This  one's at 29.5. This one's at 12.3. Someone wants
7:22:55
me to bump those all down 3 dB. Or let's make  it even harder for this guy. 3 and a half dB.
7:23:00
I select those three. I type -3.5, enter. And  I'm done. That's my favorite use of AppleScript,
7:23:10
right? Added to it doesn't make me feel stupid  every day. It also saves me some time. And if
7:23:19
I've got a complex series of cues, it can save  me a meaningful amount of time when I do it just once. And I do it all day every day when I'm in  tech. So, I'm saving enormous amount of time. I
7:23:30
do not ever want the designer who I'm assisting or  programming for to have to sit around and wait for
7:23:35
me to do something straightforward. Right? I'll  walk you through that script. Has anyone here used
7:23:45
AppleScript before? Has anyone here used any  scripting language before at all? Right. Okay.
7:23:53
really quickly. Scripting languages, the purpose  is to be light and quick. The purpose is not to
7:24:03
write a piece of software. The purpose is to  automate some action. AppleScript was invented
7:24:10
not recently, right? AppleScript is from the '9s  and um as I said before, Apple pushed really hard
7:24:17
on it for a long time and then backed off a lot on  it. Anyone who really knows how to write software
7:24:24
generally comes to the conclusion that AppleScript  is an awful scripting language. And that's pretty
7:24:29
much true. But it's also not that bad. It's just  awful. That's all. Um, and the thing is that it's
7:24:38
slow and it's clunky and it's awkward, but you  can learn it a piece at a time. And so someone
7:24:45
who is disinclined to learn about programming  might start with a scripting language where you learn a piece at a time and you can you do  useful things, build up that usefulness. For me,
7:24:57
my versatility in AppleScript is rooted 100% in the  fact that AppleScript is built into QLab. And when
7:25:05
I learn to do good AppleScript, that makes me  pop that makes it possible for me to build QLab
7:25:12
tools that make it feel to me like I've got my  own custom features of QLab built right in. So
7:25:18
here is the script that is my control L level  change script and I'm going to walk through it
7:25:24
and I'm going to try to explain the principles  without trying to hinge too hard on whether or
7:25:29
not you understand what AppleScript is. first  line tell application id com.figure53.qlab.5
7:25:40
what that says is okay AppleScript because all  this text is going to get passed to the Mac
7:25:45
OS's AppleScript interpreter which is a little  chunk of software that's built into macOS that says send me some AppleScript and I will do it.  This script says, "Okay, AppleScript interpreter,
7:25:59
this code when you run it, you're going to run it  at QLab. You're going to tell QLab to do stuff." So
7:26:07
everything between tell and tell, which is all  of this, gets aimed at QLab. Then it says try,
7:26:16
which just just try it, man. Just try. try uh  in this case means do this stuff and if it goes
7:26:27
wrong and there's an error message, I don't want  to hear about it. Just silently stop trying if it
7:26:33
goes wrong. And the reason that I put that there  is because I may run this script in a hurry with
7:26:39
uh the wrong context uh the wrong thing selected  or whatever and I don't want to hear about it and
7:26:44
deal with an error message while the the person's  breathing down my neck asking me to keep working.
7:26:49
So a important clue to writing good scripts is  never add the try until the end. Now there's a
7:26:56
thing called catch which is part of try. Try says  try this stuff and if it goes wrong don't tell
7:27:02
me. If you combine try with catch. Catch will say  and if it does go wrong do this stuff. But I don't
7:27:14
want to catch. I want to try and if failure  just fail. Goodbye. Move on because it's tech
7:27:21
rehearsal, man. I gotta go. So don't add a try  till the end of your project. Okay. Try. Now that
7:27:28
we're trying, we're going to try all this stuff in  between the try and the end try. The first thing
7:27:34
it does is display a dialogue. And the dialogue,  which means a window on the screen that's the
7:27:40
computer's going to use to talk to me. Set levels  like this and some text. And then it says default
7:27:46
answer zero with title change main level with  buttons cancel and okay. The default button which
7:27:53
is the one that will happen when I press enter is  okay and the cancel button is cancel. So what I've
7:28:00
told it is make a little screen say this stuff to  me. Expect some text from the human. If they press
7:28:07
enter it's like they click the okay button. If  they press escape it's like they press the cancel button. If they press the cancel button stop doing  stuff. If they press the okay button, keep going.
7:28:18
Set new level to text return as of result. And  what that means is new level, which is in green,
7:28:25
is a variable. What's a variable? It's a jar. You  put something in. In some programming languages,
7:28:32
you have to say what kind of jar. AppleScript?  No, you don't. What goes in there? Stuff. Could
7:28:38
be a number, could be text, could be a picture.  Who cares? We're going to figure it out later. Good programming languages say, "How could  you? That will matter later." And scripting
7:28:48
language is like, "There is no later. I'm a  script. When I'm done, I'm gone. There's no such thing as time." Anyway, set new level,  which is a variable I just made up right
7:28:59
now to the text that the person typed into the  little box and stick it in there. Okay, great.
7:29:06
Then it says repeat with each cue in selected of  front workspace as list. So to start with what
7:29:14
that means is everything between repeat and end  repeat. We're going to do it more than once. How many times are we going to do it? Well, I'll  tell you. Let's make a variable called each
7:29:23
cue new jar. And what do we put in each cue? We're  going to make a list of all the cues that are
7:29:32
selected in the front workspace. So if this  other workspace is open, I don't care about
7:29:37
those. But in the the cues you selected in the  front workspace, make a list of those cues. Put
7:29:43
that list in the jar each cue and then repeat all  this stuff once for each entry in that list. So
7:29:51
if the list is eight things, we're going to  do this eight times. And each time we do it,
7:29:56
wherever you see each cue, we're going to fill it  in with the next cue down that list of cues, right?
7:30:06
The next thing we say is if the cue type of each  cue is audio or fade or mic or video or camera,
7:30:18
which is a comprehensive list of all the  types of cues that can have a main audio level. Then we're going to tell the front  workspace, hey workspace, do this stuff.
7:30:33
If HQ is not audio, fade, mic, video, or camera,  there's no else. So, just bail and goodbye.
7:30:44
But if it is one of those types, tell the front  workspace, okay, now if the new level starts with
7:30:52
a plus, take the thing the human typed in,  add it to the current main level, and then
7:30:59
make the new main level that the result of that  addition. If it starts with minus, subtract that
7:31:06
thing from the main level of the of each cue. If it  starts with an asterisk, doesn't matter what the
7:31:14
main level is right now, set it to this value  explicitly. That's a shortcut that I decided to make because the asterisk is on the number key  right up here. So, as I was developing the script,
7:31:24
I thought, you know what, it might be nice to  say, I've got a whole bunch of cues selected and the designer says to me, hey, just set all  of those to minus12. So, I say star minus12
7:31:32
enter. Why star? Because it's convenient on the  keyboard. And then I was like, that's confusing.
7:31:39
Maybe someone's going to misunderstand it. So I  added, hey, if they type at, use that as the same
7:31:44
as star. Then I end the if statement. Then I end  the tell statement. Then I end that if statement.
7:31:55
Then I end the repeat statement. Then I end the  try statement. And then I end the tell statement.
7:32:04
This script, oh, here we go, is in a script cue. The script cue is  set to run in separate process. What that means
7:32:19
is while the script is running, it's actually  running as though it were a whole separate program
7:32:25
somewhere else. which means QLab if it's busy doing  stuff will not be held up by the script waiting
7:32:31
for the person to type in a number. That's a bit  of an oversimplification, but it's not false.
7:32:39
The script cue in the triggers tab has  a hotkey trigger L. So when I type L,
7:32:46
this cue runs. It pops up that dialogue box. I  type in a number and away to the races. Simple,
7:32:56
not that fancy, not that sophisticated,  but it really helps this guy not feel like an idiot simply because I  have a small learning disability.
7:33:08
Making a fade in or a fade out. Just take  all those cues that you meticulously set
7:33:13
your levels at. Oh yeah, that's great. Now  fade those all in from silence. Select them all. Control I. Done. One fade cue for  each fades into the level that you set.
7:33:26
I have a very very esoteric script here  called the incremental pre-wait change.
7:33:33
What if I have eight cues or more and I want them
7:33:38
all to have different pre-weights that  slowly increase? Control shift E.25.
7:33:47
Now the first cue has a pre-wait of 0.25. The  second cue has a pre-wait of 0.5 75.1 1.25
7:33:53
25 1.5 I was working on a show with a projection  design that involved lots of little colored
7:33:59
squares and I was for many scenes I was often  just popping up 50 to 90 colored squares and
7:34:06
the director said wouldn't it be nice if they  just kind of appeared across the stage like that so I wrote this incremental pre-wait script  so that I could do that and then he could say
7:34:14
faster and I would make them faster slower or  make them slower. He was a very chill director.
7:34:20
was like, "Is such a thing possible?" And I'm  like, "Scott, give me just a sec." It was He was really great. Really great to work with. Um,  what are the other ones I use all of the time? Um,
7:34:34
arming and disarming. Uh, in on MAS, there's  no keyboard shortcut for arm and disarm.
7:34:44
We do that a little bit on purpose because  disarming cues can really make a mess of things. But I added control A for arm, control  shift A for disarm. For me, it's nice to have.
7:34:58
Those are the kinds of things I use scripts for  all the time. my some of the time script. This
7:35:06
is a script called take control. When I'm in  a budget sensitive environment that is not so
7:35:13
budget sensitive that they don't want a backup  Mac in case something happens to the primary, this script allows me to automate which MAC, the  main or the backup, is the one that's actually
7:35:24
outputting messages and sounds and things. It  basically automates turning on override controls
7:35:31
on one or the other and that relies on some tricky  stuff. Um, so it's not that easy to just talk
7:35:40
through in a hurry, but I wanted to give you the  premise. Um, you already saw my cut script. Love
7:35:49
that. Uh, let's see what else do I use here.  Those are the biggies. And while we're at it,
The QLab manual - Sam's Toolbox (of scripts) - downloadable!
7:36:00
in the manual in tutorials,
7:36:06
Sam's toolbox, the level scripts, some  time scripts, some geometry scripts,
7:36:14
some workflow scripts. Oh, this one's good. This  script call causes all running fade cues and light
7:36:21
cues to rush to completion. Sometimes I'm working  on a show, I've got a 90 second fade going and the
7:36:28
designer's like, "Yeah, yeah, yeah. Let's get to  the end of that." Well, what do I do? I type shift
7:36:34
F and all the fades that are currently running  just VOP to the end. Useful stuff. Please enjoy,
7:36:43
download, tinker, learn. If you come  up with an improvement, let me know.
7:36:52
Some of these scripts I feel bound to point  out once one of these individuals asked me
7:36:57
to be more pointed about pointing it out. Some of  these scripts are built on ideas that Rich Walsh, Mick Pool, and Chris Ashworth showed  to me. So, credit where it's due.
7:37:13
I've used scripts for wackier stuff than  this. I've used scripts to arm or disarm
7:37:18
large groups of cues based upon whether or not  an understudy has gone on. Right? If I have a
7:37:26
show full of voiceovers and the understudies  on tonight, we need the understudy voiceovers.
7:37:31
Right? But I can also use OSC and wild  cards for that, right? Because I can make
7:37:38
an OSC message that's like cue. So, if my uh  what is it? What was her name? Her name uh
7:37:56
arm all the cues named Rachel something.
7:38:05
Disarm all the cues named Susan something.  Now Rachel's on. When I do the opposite,
7:38:13
all the cues named Susan something are  armed and all the cues named Rachel something are disarmed. Now Susan's on,  right? So then I just have to make sure
7:38:21
that all my voiceover cues the number is  Rachel's something or Susan something.
7:38:28
I think I had a quick and easy way to override
7:38:38
something in your toolbox. It's not  in here, but let's look real quick.
7:38:48
scripting and automation. Apple  script dictionary search override.
7:39:00
It's in the built not that this is good, but it's  built in the no definition editor. I think he's
7:39:12
Oh, in AppleScript Editor. No, just like Oh,  we're talking about AppleScript. But yeah,
7:39:17
I hear you. Thank you for that.  Yeah. So, overrides is here. Um,
7:39:28
the the the specific syntax for  override is actually a little awkward.
7:39:34
No, no, it's it's it is I mean, it is also  AppleScript's bad though, right? because
7:39:41
like the the the programming structure that's  behind the scenes about how the override panel
7:39:48
works forces the AppleScript possibilities into  a bit of a corner. And so the way AppleScript is
7:39:55
allowed to address that piece of the program  is narrower than it would be if the override
7:40:01
controller had been built some other way. And it  works very very well. So it doesn't really m but
7:40:07
this is like this is exactly where AppleScript  drives people crazy because a programming choice
7:40:12
that has nothing to do with AppleScript that  Christopher made when he built overrides forces
7:40:17
AppleScript to only use slightly awkward language  to describe overrides. I don't have is it here?
7:40:31
Oh I have it on this other computer.  here. Give me just one sec.
7:40:38
I have a good example of it and  I think it'd probably be useful.
7:40:49
Yeah. Okay. Set OSC input enabled of overrides to  false. That's that's the strange language. Set OSC
7:41:02
input enabled. of overrides. I  don't know about this keyboard, man.
7:41:13
Yeah, it's a little squishy. It's Yeah,
7:41:23
this is the language for turning  off the OSC input enabled override.
7:41:30
So you can make a script that's like set  this override to this, this override to that, that override to the other, and then when  you run that script, that's what happens.
7:41:41
Um, it's just it's just finding the  terminology and plunking it in. The
7:41:48
thing that's great about AppleScript is  part of what's horrible about AppleScript, which is if you look at a script and there's  a piece of that script that is like, "Oh yeah,
7:41:58
that's what I wanted to know." Chances are good  that you can just copy that one little piece and paste it into your script and it'll work or  work with only a very small amount of adjusting.
7:42:08
Unlike grown-up programming languages where  you're like, "Oh, no, no, this piece is actually predicated on all of those pieces and all of these  pieces have to follow after otherwise, man, you're
7:42:18
sunk." Right? So that's like real programming  is on the other hand, real programming, you can do anything. AppleScript, you can do these  things, right? So yes, the the the syntax here is
7:42:32
set OSC input enabled of overrides to false. And  here's the list under override controller in the
7:42:38
QLab documentation. DMX output enabled, MIDI input  enabled, MIDI output enabled, blah blah blah blah
7:42:44
blah. And so you set the set this of overrides to  true for overridden or false for not overridden.
7:43:00
OS. Yeah. Under the scripting and automation  head heading is our OSC dictionary which is
The QLab manual - OSC and AppleScript
7:43:09
um where are we? scripting and automation  OSC dictionary which is like a lot
7:43:20
as much as possible we try to  make it true that if you can do it in QLab you can tell QLab to do it with OSC
7:43:30
that's there an OSC queries document which  explains OSC queries which we talked about
7:43:35
in some finer detail the AppleScript dictionary  Okay, which is all of the AppleScriptable-ness of
7:43:43
QLab. This page is called parameter reference and  it's just a um reference of anywhere there's just
7:43:51
lists of stuff. So like we support scripting  of video effects, but each video effect has
7:43:58
its own weird list of parameters and their strange  scripting names and their permissible values. So,
7:44:04
I've sort of spelled all that out in one big long  document here so that if you want to script the
7:44:10
shutter parameter of a light cue that of a video cue  that has the shutter effect and you want to bring
7:44:15
the bottom shutter in, you know it's called bottom  with a capital B and you know that its range is
7:44:20
0.0 to 1.0. Whereas feather, oh, which doesn't  have two A's. Feather father can go from 0 to 800.
7:44:32
Like that's just that's what's true about  that. And then we have a little OSC and
7:44:37
scripting examples section in which I try to  do the exact same thing with AppleScript and OSC
7:44:45
for setting levels, disarming a specific  cue, creating and moving a new cue,
7:44:53
creating fade in cues. This is great. When did you  make this one? I can't remember. But thank you.
7:45:01
I wanted to do something a little beyond  like here's scripting go. It's like some
7:45:06
examples. And in the tutorial section  of the doc, there are a bunch of these
The QLab manual - Tutorials
7:45:13
um downloadable examples or videos about different  things. Not all of these got fully fleshed out. I
7:45:20
don't think I ever made zero to MIDI. Yeah, that's  not been made yet. That just didn't happen yet.
7:45:26
But the computer networking document is in there.  An expanded version of my USBC diet tribe from
7:45:32
yesterday. If that wasn't enough USBC nonsense  for you, here's the rest, including all kinds
7:45:39
of details, the really gory bits. Um, there's  a downloadable version of the blend modes um,
7:45:47
explanation. The blend mode demo lets you use  those two videos that you saw me demoing and
7:45:54
flip through different blend modes with keyboard  shortcuts. What else do we have in here? Sam's
7:46:01
toolbox. Um, there's some time code tools for  capturing incoming time code and stamping cue
7:46:06
triggers with them and exporting a CSV list of  time code triggers so that you can give it to the
7:46:11
um, lighting design assistant so that he knows  exactly which frame you're expecting because I say he because it was Aaron who asked me for  this. Um, not this Aaron, a different Aaron. Um,
7:46:23
so these are all available uh in the doc and we  are slowly but surely working on more of them.
7:46:33
What else?
Our brains are full... other resources for learning about QLab
7:46:40
Brain saturation. Yeah, the sponge, you know,  ultimately gets full and then no more water
7:46:47
can go in. And our spongy brains are not that  different. There's like a speed at which you
7:46:53
can receive words from someone else. Um, Um, in  addition to the documentation, we're starting to
7:47:03
try to put out some video tutorials. So, if you go  to qlab.tv, you could watch the stream that you're
7:47:10
in right now and or uh other video tutorials. So,  that's that's us now. Oh, wow. That recording the
7:47:23
recording that's headbending the recording of this  class. We leave the recordings up. If you want
7:47:30
to go back to something you remembered from this  class, you can go back and find it. Um, I'm trying
7:47:37
to put out some more video tutorials on occasion,  such as those those ones about object audio,
7:47:44
etc. And some of these that feel more sort of  like documentation-y I'll link directly in the
7:47:52
doc. Other ones like visualizing object  audio in QLab 5.5 feels like more of a topic that's like understanding this topic  which to me doesn't feel directly relevant
7:48:01
to the documentation. So some of them will get  linked but all of them are available at QLab.tv.
7:48:13
Um, all right. I don't want to like rush to the  end of this thing, but I do want to make sure
7:48:19
that this I'm in audition mode. I do want to make  sure that this slide gets up before we leave. So,
Contacting us
7:48:27
this doesn't mean you have to go. But, um, I do  want to make sure that it is as clear as possible
7:48:34
how to reach us because I keep saying ask us, send  us something, tell us something. If you want to
7:48:40
talk to me directly, samfigure553.com is my email  address. Hear my words, friends. I do not respond
7:48:48
to urgency in this email address. If you have  an urgent question, you absolutely should write
7:48:56
to supportfigure53.com. If it is between 9:00  a.m. and 900 p.m. on a regular workday that is
7:49:04
not a federal holiday in the US, you will get  an answer almost certainly within 10 minutes.
7:49:09
sometimes faster and we more or less promise  within an hour. If it is not during those times,
7:49:17
the answer will come as soon as we can. If you are  not in a burning hurry and it is okay that you get
7:49:25
an answer slowly, feel free to write me. If you  have feedback about this class that you want to
7:49:31
send not directly to me but you maybe want to  send about me or about any other thing. If you
7:49:37
want to send it semi-anonymously, you can send  it to Cricket. It is semi- anonymous in so far as
7:49:43
Cricket will hear will receive your email and  know it's you. But Cricket will not tell anyone else that it's you who said it. So it is not  anonymous from Cricket. But let me tell you if
7:49:53
she's not trustworthy, no one is. So Cricket is the  way to get feedback to about me or about the class
7:50:00
that you want to keep private. If there's feedback  that you want to send about the class that is not
7:50:05
private, you can tell me exactly what you think.  You can tell support what you think. If you tell support something you think and we might quote  you in public if it's all right with you. Um,
7:50:16
but really I want to emphasize if you have  trouble with QLab at any time, whether or not you
7:50:21
have bought a license, whether or not you think  the problem is quote unquote a stupid question,
7:50:26
um, I genuinely believe some people say there are  no stupid questions. I'm I'm not going to go that far. There are stupid questions. I've been asked  stupid questions. But there's no stupid question
7:50:34
that comes from someone who thought about that  question for just a second and then decided to ask it. That's not a stupid question. It could  be a simple question. Could be a basic question.
7:50:43
It's not a stupid question. You thought about it  for a second and thought, I want to know this. That's not stupid. That's never stupid. So,  feel free, no matter how small and no matter
7:50:54
how big. You think this is not going to No way.  But we love those questions. We do. Some of us
7:51:01
love them more than others. Some of us love them  more than others on certain days. And that's why we're a big team. Then we pass it around. And who  feels ready for a question of this sort today? Oh,
7:51:10
I do. Great. It's yours. That's why support is  a group and um we take this stuff seriously and
7:51:16
we like to take it seriously. So I wanted to  make sure to put the slide up before we split, but I also want to make sure not to split early.  And if anyone wants to talk about anything else,
7:51:25
let's keep talking, but I didn't want to skip over  that. Yeah. Thanks. Yeah. I guess I've sort of
QLab-specific hardware
7:51:36
gleaned that our friend Alec back here has already  produced some hardware that is specific to QLab. I
7:51:44
I I suppose I don't remember what exactly it is.  I make media servers for with Max. Yeah. So this
7:51:51
this box it's called the showcase. It contains  a Mac Mini and some other gak that's useful.
7:51:59
Um, remember I said sometimes there's IT  departments who we don't get along with. Does
7:52:08
anyone not know that the ETC ION is in fact  a Windows computer? If you don't know that,
7:52:14
now you know that an ETC Ion is just a Windows  computer with a very expensive keyboard attached.
7:52:23
It is not just in so far as they've done an  incredibly good job of engineering it. And um but
7:52:31
here's what happens. IT department comes in, sees  a computer and says, "We have rules about that. Install this ridiculous anti virus software and do  this and do that and we care a great deal." They
7:52:40
look at the lighting console and they're like,  "That's a lighting console. I don't know what that means." And they leave. Alec thought, wouldn't  it be nice if they looked at this thing and said,
7:52:50
"I don't know what that is and I don't care." And  they leave. Voila. This is your friend. This is
7:52:56
not a Mac. It's not a computer. It's a theatrical  show control device. This is a QLab media server.
7:53:03
What's a media server? I don't Sounds good. I  don't know. What's a media server? My DVD rack is
7:53:09
a media server. Kind of. Um, this is a QLab device.  It's really just a Mac Mini in a good box. So,
7:53:17
this is QLab specific. I build these because I  want them to exist and no one else is building
7:53:23
them so they exist. This is not QLab specific but  it's made to work well with QLab. So I guess that
7:53:29
like gets to like another part of my question  is like um specifically with lighting I could
7:53:35
see I mean also audio of course but that seems  a little more direct. Is there um third party
7:53:42
hardware that is just a bank of sliders and some  knobs and some buttons that that I can that I can
7:53:50
then like program like total general purpose that  I can program and attach to QLab to like help a
7:53:57
lighting designer who wants more fiddly knobs and  you know because like it seems to me in general
7:54:03
um uh the expectation for additional controls like  really helps workflow with lighting. I'm not a
7:54:10
lighting person trying to like get QLab to help me  do lighting better. Is that something that is like
7:54:15
available or easy to like connect to cue Lab? Sam,  did you pay him? I did not pay him. Am I either
7:54:23
or do you make those? Is that Oh, can I Where can  I buy one, sir? First of all, because I feel like
7:54:32
just because I want to be on the up and up about  this, right? I work for Figure 53. Alec works for
7:54:38
Figure 53 in a sense. Alec works for the Voxel.  We are employees of QLab, but I got a side hustle
7:54:48
because it's this decade. This is my side hustle.  Uh teams sound.nyc is the website of this company.
7:54:58
Myself, Alec, Mike Deyo, Alana Jacoby, and our dog  Rocket are the, and sometimes Evan Cook, are the
7:55:09
Team Sound group. Team Sound makes these button  boxes and Alec and we collaborated on the Pilot,
7:55:17
which is a motorized MIDI fader surface  designed specifically to work with QLab, specifically QLab lighting, but it also works well  with EOS and with Yamaha consoles. like, dang,
7:55:27
I wish there was something where I could just have  a bottle. I feel honor-bound to also point out that there is a really really inexpensive non-motorized  fader surface made by Akai that's dynamite. So,
7:55:39
if you want to like go dirt cheap and physically  small, that little tiny AAI fader thing, that's
7:55:45
great. No knocks, no notes. Very, very impressed  with that. Highly recommended. I wanted very hard
7:55:53
to be able to recommend a motorized MIDI surface  that before the pilot existed. I really wanted to
7:56:00
and I scoured the earth and I could not find one  that I really really liked which is why I was so
7:56:05
excited to work with Alec on making the pilot. But  um that doesn't mean it's not out there. I just
7:56:11
haven't found it. So if there's another motorized  MIDI surface that anyone knows about that really is the bees knees, I'd love to know. Um, but  for my money, the point of the pilot is not so
7:56:25
much that I'm trying to hawk my own thing. The  point of the pilot is it was designed in answer to the question that you asked specifically.  So, um, so that's among my answers, but the
7:56:37
Akai thing is really quick and dirty and cheap.  Um, anything that makes I I don't mean cheap,
7:56:43
flimsy. I mean cheap, inexpensive to be clear. Um,  anything that speaks MIDI is going to get the job
7:56:50
done. Um, as for other sort of QLab specific  hardware, like basically no, right? Like we
7:56:59
um all the all the theatrical stuff that seems to  have super specific hardware, it turns out is all
7:57:07
Windows, right? the EOS Windows, Pixera Windows,  uh GrandMA Linux, uh not Windows, um D3 Windows,
7:57:18
right? So, it's all like um and that comes with  like some pluses and minuses. On the plus side,
7:57:25
folks like Watch Out can build the Watch Out PC of  their dreams that's all locked down and works just
7:57:31
like they like and they can sell it to you for  a nice comfortable markup. But also, you get a
7:57:36
computer that definitely works right with Watch  Out. Okay, it's good. On the other hand, you
7:57:42
have to use Windows, which is a punishment that I  don't want to put on anybody. And um Windows for
7:57:49
whatever other good or bad things are true about  it, I think is ugly. And more important to us,
7:57:58
all of our developers are very good at developing  software for the Mac. The Mac comes with a lot of things in it that our software is built upon that  are really useful. The core audio engine that is
7:58:09
built into macOS is what makes all of our audio  features possible because it's this like reliable
7:58:16
bedrock layer that we hook onto. We do stuff  and we say, "Hey, Core Audio, do this for me. Do that for me." Ditto MIDI, Ditto video, right?  And they've built a like great foundation for us
7:58:27
to build on. I'm not saying it's impossible  to do good work on other platforms at all,
7:58:33
but this is the way we've built ours. Um, the flip  side is no one builds Macs but Apple. So, Alec has
7:58:42
shown us a way around kind of if you don't look  too close, which I think is fine. For a while,
7:58:47
PRG made a really cool automation console that  was this great looking sort of space age rocket
7:58:54
ship controller thing. If you pop open the lid,  there's a couple of Mac minis strapped down with plumbers's tape. Yeah, super like points for  points for the the chutzpah to just literally use
7:59:07
plumber strap in there. I was like, "All right,  guys." Um, but the console worked great, don't get me wrong, but no one would confuse it for a  Mac, right? So, the IT folks look the other way.
7:59:21
That's your weird wishy-washy answer without  a good punch line. thinking it would be cool
7:59:27
to have a controller. It sounds like you had  the same time at some place in the past. So, good for you. Um, folks who are watching from the  UK, there's a company called That Little Box and
7:59:37
they make boxes like this in the UK. Um, and so  that's another option. And uh there is at least
7:59:44
one person on Etsy who makes um some 3D printed  goofball box that has, you know, there's nothing
7:59:55
wrong with it, but 3D printed to me always sort  of feels like could break at any moment and no
8:00:01
one would know why. And um maybe it's great,  don't get me wrong. Um but that gives me that
8:00:07
feeling. Um so there's other stuff out there.  Um, but I will say and make a point of saying
8:00:14
there's no hardware that we we QLab specifically  approve of or disapprove of. If it works with QLab,
8:00:23
we're thrilled. If it doesn't work with QLab,  we encourage you not to use it. Um, but there's
8:00:30
nothing that's like specifically blessed by QLab.  There's nothing that specifically has hooks in QLab
8:00:35
to work with QLab other than the USB DMX devices  that we talked about before, the video devices
8:00:42
from Blackmagic that we talked about and NDI and  um we actually use some third party libraries
8:00:48
for MIDI and stuff like that, but NDI is not a  great example, but the Blackmagic devices and
8:00:53
the USB DMX devices are the closest we can get to  hardware that's specifically thumbsed-up by QLab.
8:01:03
Am I missing something on that one? No. Yeah. All  right. If you find some gear that works great with
8:01:09
QLab, use it and let us know about it. We did  recently publish a Stream Deck plugin at the
8:01:16
urging of the Stream Deck people. Um, the folks  who make the Bit Focus companion QLab plugin,
8:01:22
that's not us, but we think it's great.  Um, some folks like it, great, use it.
8:01:29
I'm really interested in the new stream deck  that has the good scissor switches because my only problem with the stream deck is that when  you hit the edge of the key, you don't really
8:01:38
hit the key and it's got this kind of gummy  squishy feeling. So, I haven't gotten one yet, but I'm excited to try it. Yeah, I'm enthused  about it. Yeah, that's my guy. All right. Anything
8:01:53
else? As you can see, we are now well into the any  topic at all. truly section of the conversation.
8:02:03
Yeah. When you were talking about like Google  Drive, have you noticed any of that with like
8:02:08
desktop backups or like sync in fact desktop  sync kind of? Yeah. I just like Apple the the
8:02:21
the hook that macOS gives you to say is this file  actually here or is it promised to be here in the
8:02:28
future? That doesn't always tell us the real  truth. And so I don't love it. I would love it
8:02:36
to be just definitely very obvious. Is this file  on this computer or not? And I don't understand why that's such a controversial opinion. Right?  It's the same thing with my problem with LLMs.
8:02:45
Is this the answer or is this not the answer? I  don't I don't understand why needing to know is
8:02:51
like, well, you know, that's that's a tall order,  Sam. No. Is the file on the computer or not? So,
8:02:57
that makes me it makes me anxious.  But, um, if you uh in iCloud Drive,
8:03:07
you can set a file to...  Where is it? Keep downloaded.
8:03:16
and a file set to keep downloaded in macOS gets  this little uh tra-la-la widget here. And that is
8:03:23
trustworthy as far as I can tell. I've been using  um I use a piece of software called Obsidian for
8:03:29
note taking. And when I turned keep downloaded on  for the Obsidian folder on my Mac and my iPad,
8:03:37
all of my woes about synchronizing, all of my woes  about synchronizing my notes across two devices
8:03:45
vanished. So for me, this keep downloaded  feature, which was fairly recently added,
8:03:51
really helps. Really, really helps.  My skepticism of Google Drive remains,
8:03:59
but not for non-QLab stuff like use it  for regular stuff by all means. You know,
8:04:07
the other thing about desktop and documents  back up to the cloud is if I use a show Mac
8:04:15
that's rented and I need my files, I do I  sign into my account on that Mac? And if so,
8:04:23
does all my other stuff from my desktop and  documents folder appear on that Mac? Some of that might be personal. I don't like that. So, it  makes me a little jumpy even if it works perfectly
8:04:34
because of the mixture of the way that I use my  Mac as a personal tool and as a professional tool.
8:04:44
What else? Does the internet have anything  to say? That's that question. And the answer
8:04:50
to that question is always yes. But does the  internet have anything to say to us at this time?
8:04:57
Someone on the internet mentioned  orbital nemesis make a good video box.
8:05:12
Oh yes, Nemesis. They make great stuff. Do  not at this time ask how much it costs. Wait
8:05:22
until you are sure you want it before  asking how much it costs because then you will be unable to deny yourself and  it won't matter how much it costs. Um,
8:05:31
no. Ne Nemesis Research makes great stuff  for sure. I am glad someone mentioned that. And they have these uh groovy button boxes  that are highly programmable and use OSC. Um,
8:05:42
little little more industrial vibe than these.  Um, but there's nothing wrong with that at all.
8:05:49
Yeah. Nice. And it's highly  commended by the Association
8:05:55
of British Theater Technicians. So that's
8:06:04
there was a question also about which Blackmagic  device did you use for the camera demo yesterday?
8:06:11
I think it was Yes. Okay. So, in Blackmagic,  blackmagicdesign.com products capture and
8:06:23
playback, the UltraStudio 3G has uh a range  of products. And going all the way down to the
8:06:34
bottom here, tra-la-la we have the UltraStudio Recorder  and the UltraStudio Monitor. Recorder is video
8:06:40
coming into the computer. Monitor is video going  out of the computer. These are they this media
8:06:49
server contains two of one and one of the other  at the moment but it's sold by default as three
8:06:55
of one or three of the other. The UltraStudios  the other UltraStudios, UltrasStudio? I don't know
8:07:05
have other capabilities; all of them work.  Basically, any device made by Blackmagic that
8:07:13
has the name UltraStudio or Intensity  or DeckLink is compatible with QLab. So,
8:07:23
I have at home a Thunderbolt chassis. It's a box  like this. It's got PCI card slots and it connects
8:07:30
to my Mac with Thunderbolt. I put Well, they don't  have the one I put anymore. I have a much a less
8:07:39
a less extreme a not extreme. I have a DeckLink  duo card in there. It's got four SDI sockets on it
8:07:48
and it's configurable dynamically. Each of those  four is either an input or an output up to 1080p
8:07:55
on SDI. So, when I have that box connected to my  Mac, I have four inputs or outputs. Um, I love it.
8:08:04
It's really quick and easy. The external box is a  little clunky. It's got its own power supply. It's not super portable. It's not quite as slick as  this, but it gets the job done. Most definitely.
8:08:23
I have not tested it with a 2110 card. Um 2110  in case anyone is curious. 2110 is like um NDI
8:08:32
is a proprietary video over IP system. Dante it's  a proprietary video audio over IP system. AVB is
8:08:41
an open standard that competes with Dante. 20010  is an open standard that competes with NDI kind
8:08:48
of. And um 2110's appealing for a lot of reasons.  Um, I don't I haven't encountered any 2110 gear,
8:08:57
so I haven't had any reason to test it,  but it's interesting to me. I like SDI,
8:09:03
man. The cable's cheap, goes a long way. It's  hard to break, and if you do break it, it's easy to fix in the field. Yeah. What? I said, I don't  know why anyone does anything else. Yeah. Well,
8:09:14
because sometimes you don't want a broadcast  resolution. Sometimes you want 1920 x 1200.
8:09:23
And you can't do a non-bro resolution over  SDI. Not really. I mean, you can, but you
8:09:29
have to make it. You have to trick it. Yeah. Um,  I think 2110 is interesting, and as time goes on,
8:09:35
if people really adopt it, I'll be enthused  about that. The same way I feel about AV, right? Like Meer Sound has AV built into their  hardware. Dope. How do I plug into that? Right
8:09:47
now, I use an orange box, which is an expensive  device by DiGiCo, which converts something else to
8:09:52
AVB. I don't love that. I don't love that. I  don't love that I have to do that. But I got
8:09:59
nothing against AV. I think it's great.  And when more stuff supports it, I'm in.
8:10:06
Did you talk about edge blending? I can't  remember. We don't have Yeah. more than one
The Voxel's edge blended eight-projector system
8:10:12
projector. I'll just mention then if you're ever  in this room when there's not a bunch of tables. If you look in the ceiling above you, there's  eight projectors hung above the grid. Those
8:10:22
are all connected to one Mac studio backstage  and they're all hitting the floor in such a way that they overlap a little bit. And one of  the things that QLab can do is if your regions
8:10:32
that if you remember from yesterday, your stage  that you put uh rectangular regions on, if those
8:10:38
regions overlap a little bit, QLab will do a  crossfade, like an edge blend on that overlapping
8:10:44
section. So you can use multiple projectors  to pretend to be one big projector. And so Oh,
8:10:52
Alec is turning them on. We go dark. Sure. It'll  be hard to see because there's tables here, but
8:10:59
um then what effectively can happen is that  that one Max Studio can can present all eight
8:11:07
projectors as if they're one giant NDI screen.  And so the artists working here can send imagery
8:11:15
or do all kinds of fun stuff. So this is the un  Okay, this is fun. Actually, you can kind of see.
8:11:20
So this is the this is the raw output. Actually,  can you just go back to the Yeah. So, this is the
8:11:27
raw output of the A projectors. If you see on the  floor, each color is one projector. It's the full
8:11:32
raster of the projector. You can see that they  land in kind of warped funny ways. They overlap
8:11:39
each other. If you tried to project just straight  out like this, it would look pretty bad. They'd
8:11:46
bleed up on the side of the curtain. All kinds of  stuff. Um this is the raw output state of those
8:11:52
eight projectors hitting the floor in because okay  so in QLab we now have those that raw output state
8:12:00
and do all the stuff that Sam talked about with  warping and overlapping the regions so that the
8:12:07
um what are we going to go to next do you think?  turn off the grid. So, we'll go I guess we'll take
8:12:14
off the the route outline colors and go to the um  the grid, which is the the corrected version of
8:12:22
the output, which should be roughly aligned.  There's always a little little wiggle room,
8:12:31
uh but roughly now that fixes that fixes the  warping. So now uh it stops at this at this
8:12:40
corner of the curtain instead of going you know  here's where the projector hits where this orange line hits but because of the warping in QLab we  stopped it at the edge of the stage and where it
8:12:52
crosses over into where another projector  starts projecting. They've been warped so
8:12:58
that they pretty close to line up. There's maybe  some spots there's maybe a centimeter or two off,
8:13:03
but it's pretty close. And it therefore becomes  effectively one giant projector out of eight real
8:13:12
life projectors. And uh then it's just a giant  screen that you can put stuff on. So I don't
8:13:18
know here. Oh yeah. So like the ocean. I went on  vacation once and sent a drone up in the air for
8:13:27
about 20 minutes and just pointed it downwards and  got this footage of the ocean and brought it back and now we have this sort of trippy ocean thing  that we can play. We've had um we've had artists
8:13:39
do all kinds of fun stuff. They either sometimes  they'll use it during a show to as a lighting
8:13:45
effect. Uh it can be used as house lights. uh it  can be used. One really fun thing is we've had
8:13:54
artists project their blueprints onto the stage  at full uh at full scale so that you can bring the
8:14:03
set off the truck and put it where the blueprints  say to go because it's just outlined and drawn on
8:14:09
the stage. Um, you can project the grid lines  onto the stage so that when you're driving the
8:14:14
scissor lift around, you can park between the grid  without having to guess exactly where you are. Um,
8:14:23
so it's a fun it's a it's a fun tool  that we found a lot of uses for. And
8:14:29
um all you need is eight relatively inexpensive  projectors, some some vibration isolation springs,
8:14:36
which we found out when we first attached those  projectors to the building steel and a truck would drive by that they would wiggle. So we had  to put them on springs so they wouldn't wiggle.
8:14:46
And one Mac Studio can can drive that whole thing.  So that's edge that's the the fun of edge blending
8:14:53
is take a bunch of little projectors and make  one giant projector. Oh yeah, that's the other thing. Thank you, Alec. When we have artists come  in who are trying to visualize where they want to
8:15:04
perform or how they want to lay out the space, we  can very quickly show them five or six different
8:15:09
stage layouts and seats and how many seats. So  like if the if the stage is at this end and this
8:15:15
these are actually the size of the seats and  we can say, "Okay, dear dear artistic director,
8:15:21
this is what 60 seats would look like over here.  This is how much playing space you'd have." and
8:15:26
they say, "Oh, no. I don't like that. I want to  have it in a alley style." We go one moment. We'll press the button for alley. There we go. Now,  we've rearranged the room in two seconds flat.
8:15:36
And you can try that out. So, it's a fun tool.  Um, we if you have a space that you're building
8:15:42
and you want to make something like this, let  us know just because people have been so excited about it. And I've not seen it anywhere else. It's  It's so useful. So, for stage managers, two shows
8:15:56
at once without re-taping. It's It's fun. It's  fun. So So edge blending a little superpower
8:16:03
that we didn't get a chance to talk about, but is  is one one other fun little demo we can I guess.
8:16:09
Now I feel like if you're using edge blending in a  show, which I do all the time, one thing you have
8:16:15
to remember is that you are increasing the number  of single points of failure in your show. Right?
8:16:21
If your show relied on this ceiling projection,  if any one of these projectors goes down for any
8:16:28
reason, then your your look is spoiled. I'm  not saying I think that that's a reason not
8:16:33
to do it at all. I am saying don't forget that  that's so um if you are doing um there's there
8:16:42
Panasonic and Barco both make a couple of kind  models of projector that has more than one lamp
8:16:47
in it and you can either run all lamps at once  for maximum brightness or you can run one lamp
8:16:54
and keep the other on hot standby and if the lamp  dies the other lamp will pop on and take over. So,
8:17:02
the more projectors you're using with that  don't overlap, the more you risk a single
8:17:08
lamp spoiling your night. So, the more important  it is to use something like a laser projector, which doesn't burn out, or a multi-lamp  projector with fall over like that.
8:17:18
I learned when I was in Las Vegas teaching  a QClass for Cirque du Soleil that the projector
8:17:25
budget of the Chris Angel Cirque du Soleil show was, um  they spent six figures a year on lamps
8:17:36
100 plus a year more than  $100,000 a year on lamps.
8:17:44
Uh they had 60 projectors in the show. Was  that to make him look magical? That was to
8:17:50
make him look magical. That was to disguise all  the... never mind. Um the thing that now they also
8:17:57
didn't tolerate a lamp going below 80% of use  because the brightness of lamps falls off in a
8:18:05
nonlinear way. So for them, 80% was the minimum  brightness they're willing to tolerate and they
8:18:10
have all the money they need. though. But the  point of the story is not so much that they spent
8:18:15
a giant fortune is that they had a big projection  show and suddenly they had a big logistics issue,
8:18:22
which is the long-term maintenance of lamps  becomes a thing. The way that these are used here, it's not quite the same story. And this is  not a reason not to do it. Do it. It's I mean,
8:18:31
look how cool it is, right? Um, but don't wander  into it without thinking about what else do I
8:18:38
need to worry about down the way. Um, and like  alignment is an issue. So at the French castle,
8:18:46
we have 16 projectors that are aligned. Every  year they have to teach the new crew because
8:18:51
they just hire seasonal crew how to do alignment  maintenance. It's not a lot of fun for them,
8:18:57
right? So it's just a thing you have to think  about in your system. Alignment maintenance here,
8:19:03
this system was, you know, this is a more of  a closed context than the French castle. So,
8:19:09
it's not quite as anxiety inducing, but like you  talked about the truck and then the springs, like that was a small step. We've learned a lot of  things here from doing it that are valuable. Um,
8:19:20
so this is this is do it cautiously is my  recommendation. Well, I think we have come
Goodbye and thank you
8:19:29
to an end. Thank you so very much for coming. um  really really appreciate the time that you took to
8:19:38
be here. I really appreciate your questions and  your willingness to engage. Um this class is so
8:19:44
much more interesting when that's how it goes. And  I really appreciate that. Um reach out. Don't be
8:19:49
a stranger. Keep in touch. If you're ever in town  and when we're doing something you drop by, say, "Hey, absolutely." I myself am a New York uh based  person. If you're ever up in New York, give me a
8:20:00
shout. let me know by all means. And if you have  those way homers, ask. Yeah. All right. Take care.
