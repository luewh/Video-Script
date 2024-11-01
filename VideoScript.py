# dependencies
from ffmpeg import probe
from alive_progress import alive_bar

# built-in
from pathlib import Path
from datetime import timedelta
from shutil import rmtree
from os import walk, mkdir, system, rmdir, remove, listdir
from os.path import isdir
from copy import deepcopy
from time import time, sleep
from winsound import Beep
from math import ceil



class VideoScript():
    """
    Class for video processesing

    Attributes:
        path (str):
            absolute folder path of running script

        vList ([{"name":"v1",...},{"name":"v2",...},...]): 
            list of dictionnary contanning info of scanned videos

        vType ([str]):
            supported video type are .mp4 and .mkv
        
        folderSkip ([str]):
            self generated folders, skiped when scanning

        optimizationTolerence (float):
            do not optimize if optimizedBitRate * optimizationTolerence < bitRate

        highQualityParam (str):
            _
        
    """

    def __init__(self, file:str=None) -> None:
        """
        Initialises attributes

        Parameters:
            file (str): need to be set as __file__ if class is imported
        """

        if file == None:
            self.path = str(Path(__file__).parent.resolve())
        else:
            self.path = str(Path(file).parent.resolve())
        
        self.vList = []
        self.vType = ["mp4","mkv"]
        self.folderSkip = ["optimized", "resized", "upscaled", "interpolated", "merged"]

        self.optimizationTolerence = 1.15

        self.highQualityParam = (
            ' -cq 1 -preset fast -tune hq'
            +' -rc vbr -rc-lookahead 1024'
        )


    def noticeProcessEnd(self):
        Beep(440, 1500)
        # input('Press enter to exit')

    def setPath(self, path:str="") -> bool:
        """
        Set attributes path, return setting result

        Parameters:
            path (str):
                set to "" will use __file__ as default path
        
        Used attributes:
            path
        """
        if path == "":
            self.path = str(Path(__file__).parent.resolve())
            print(f'Path set to default "{self.path}"')
            return True
        else:
            if isdir(path):
                self.path = path
                print(f'Path correctly set to "{self.path}"')
                return True
            else:
                print("Path do not exist")
                return False
    
    ##################
    # region Get Video

    def getVideo(self, folderDepthLimit:int=0):
        """
        Set attributes vList's path and name by file scan

        Parameters:
            folderDepthLimit (int):
                limit the scan depth
        
        Used attributes:
            path
            vList
            vType
            folderSkip
        """
        # empty video list
        self.vList = []

        for root, _, files in walk(self.path):
            # get current root's depth
            currentDepth = len(root.replace(self.path,"").split("\\"))-1

            # skip too deep folder
            if currentDepth > folderDepthLimit and folderDepthLimit != -1:
                continue
            # skip folder
            skip = False
            for folderSkip in self.folderSkip:
                if root[-len(folderSkip):] == folderSkip:
                    skip = True
                    break
            if skip:
                print("Skiped")
                continue

            # get videos
            for file in files:
                fileFormat = file.split(".")[-1].lower()
                if fileFormat in self.vType:
                    self.vList.append({
                        "type" : fileFormat,
                        "path" : root+"\\"+file,
                        "name" : (root+"\\"+file).replace(self.path+'\\','').replace('\\','__')
                    })
    
    def getVideoInfo(self):
        """
        Set attributes vList's video properties with ffmpeg probe
        
        Used attributes:
            vList
        """

        # get info
        for videoIndex in range(len(self.vList)-1,-1,-1):
            try:
                # get video probe
                videoProbeTemp = probe(self.vList[videoIndex]["path"])
                # get first video stream info
                videoStreamTemp = [streams for streams in videoProbeTemp['streams'] if streams['codec_type'] == 'video'][0]
                # get video format info
                videoFormatTemp = videoProbeTemp['format']
                # write info
                self.vList[videoIndex]['duration'] = timedelta(seconds=round(float(videoFormatTemp['duration']),3))
                self.vList[videoIndex]['bitRate'] = int(videoFormatTemp['bit_rate'])
                self.vList[videoIndex]['width'] = int(videoStreamTemp['width'])
                self.vList[videoIndex]['height'] = int(videoStreamTemp['height'])
                frameRateTemp = videoStreamTemp['r_frame_rate'].split('/')
                self.vList[videoIndex]['r_frame_rate'] = round(float(frameRateTemp[0])/float(frameRateTemp[1]),2)
            except Exception as e:
                print(e)
                print(f'Can not get video info of "{self.vList[videoIndex]["name"]}"')
                # delete errored video
                self.vList.pop(videoIndex)

    # endregion get video
    #####################


    ##################
    # region Processes

    def getFrames(self, video:dict):
        """
        Transforme video to frames

        Parameters:
            video (dict):
                info of one video. path, name, r_frame_rate are used
        
        Used attributes:
            path
        """

        name = video['name']
        path = video['path']
        frameRate = video['r_frame_rate']
        duration = video['duration']

        frameOutputPath = self.path+'\\{}_tmp_frames'.format(name)
        # check if get frame is necessary
        if isdir(frameOutputPath):
            # less than what it should has
            if len(listdir(frameOutputPath)) < int(duration.total_seconds() * frameRate):
                print("Missing frames, regenerate frames needed")
                rmtree(frameOutputPath)
            else:
                print("No need to get frames")
                return

        # create new temporary frames folder
        mkdir(frameOutputPath)
        command = (
            'start /min /wait cmd /c " {}:'.format(self.path[0])
            +' & cd {}'.format(self.path)
            +' & ffmpeg -hwaccel cuda'
            +' -i "{}"'.format(path)
            +' -qscale:v 1 -qmin 1 -qmax 1 -y'
            +' -r {}'.format(frameRate)
            +' "{}_tmp_frames/frame%08d.jpg" "'.format(name)
        )
        print(f'Getting Frames of "{name}"')
        system(command)
        print("Done")

    def frameWatch(self, outDir:str, total:int):
        """
        Track video frame process with progress bar

        Parameters:
            outDir (str):
                process output directory, where progress increase
            
            total (int):
                when to stop
        """
        
        alreadyProgressed = len(listdir(outDir))
        restToProgress = total - alreadyProgressed
        print("Already progressed : {}/{}".format(alreadyProgressed, total))
        print("Rest to progress : {}/{}".format(restToProgress, total))

        progressedPrev = 0
        with alive_bar(total) as bar:
            if alreadyProgressed != 0:
                bar(alreadyProgressed, skipped=True)
            while len(listdir(outDir)) < total:
                sleep(3)
                progressed = len(listdir(outDir)) - alreadyProgressed
                if progressed - progressedPrev != 0:
                    bar(progressed - progressedPrev)
                progressedPrev = progressed

    ####################
    # region - -optimize
    def optimize(self, quality:float=3.0):
        """
        Reduce video bit rate

        Parameters:
            quality (float):
                video bit rate = width x height x quality
        
        Used attributes:
            path
            vList
            optimizationTolerence
            highQualityParam
        """
        # create output folder
        if not isdir(self.path+'\\optimized'):
            mkdir(self.path+'\\optimized')
        
        for index, video in enumerate(self.vList):
            
            path = video['path']
            name = video['name']
            width = video['width']
            height = video['height']
            bitRate = video['bitRate']
            frameRate = video['r_frame_rate']

            # show current optimizing video
            print('--- {}/{} ---'.format(index+1,len(self.vList)))
            print(name)
            print('{}x{}'.format(width, height), flush=True)

            # compute optimization bit rate
            optimizedBitRate = width * height * quality
            # save and show bit rate change
            optimizedBitRateText = (
                '{:_.0f} --> {:_.0f} Kbits/s'
                .format(bitRate/1_000, optimizedBitRate/1_000)
            )
            self.vList[index]['optimizedBitRate'] = optimizedBitRateText
            print(optimizedBitRateText)
            bitRateParam = f'{optimizedBitRate} -maxrate {optimizedBitRate} -bufsize 800M '
            
            # check if optimization needed
            if optimizedBitRate * self.optimizationTolerence > bitRate:
                print('Skiped')
                # recored no optimization needed
                self.vList[index]['optimizeTime'] = '0'
                continue

            optimizeTime = time()

            command = (
                'start /min /wait cmd /c " {}:'.format(self.path[0])
                +' & cd {}'.format(self.path)
                +' & ffmpeg -hwaccel cuda'
                +' -i "{}"'.format(path)
                +' -map 0:a? -map 0:s? -map 0:v'
                +' -c:a copy -c:s copy -c:v hevc_nvenc {}'.format(self.highQualityParam)
                +' -b:v {}'.format(bitRateParam)
                +' -r {} -y'.format(frameRate)
                +' "optimized\\{}" "'.format(name)
            )
            print(f'Optimizing "{name}"')
            system(command)
            print("Done")

            optimizeTime = time()-optimizeTime
            optimizeTime = timedelta(seconds=round(optimizeTime,0))
            # recored optimization result
            self.vList[index]['optimizeTime'] = str(optimizeTime)
            print("Took :", str(optimizeTime))
        
        # notice optimization end
        self.noticeProcessEnd()
    # endregion optimize
    ####################

    ##################
    # region - -resize
    def resize(self, rWidth:int, rHeight:int, quality:float=3.0):
        """
        Resize video

        Parameters:
            rWidth (int):
                -1 to let it by default

            rHeight (int):
                -1 to let it by default

            quality (float):
                video bit rate = width x height x quality
        
        Used attributes:
            path
            vList
            highQualityParam
        """
        # create output folder
        if not isdir(self.path+'\\resized'):
            mkdir(self.path+'\\resized')
        
        for index, video in enumerate(self.vList):
                
            path = video['path']
            name = video['name']
            width = video['width']
            height = video['height']
            bitRate = video['bitRate']
            frameRate = video['r_frame_rate']

            # show current resizing video
            print('--- {}/{} ---'.format(index+1,len(self.vList)))
            print(name)

            # compute rWidth and rHeight
            if rWidth == -1 and rHeight == -1:
                widthTemp = width
                heightTemp = height
            elif rWidth == -1:
                widthTemp = ceil(width * rHeight/height)
                heightTemp = rHeight
            elif rHeight == -1:
                widthTemp = rWidth
                heightTemp = ceil(height * rWidth/width)
            else:
                widthTemp = rWidth
                heightTemp = rHeight
            
            # to positive size
            widthTemp = abs(widthTemp)
            heightTemp = abs(heightTemp)

            # even widthTemp and heightTemp
            if widthTemp%2 != 0:
                widthTemp += 1
            if heightTemp%2 != 0:
                heightTemp += 1

            # ratio warning
            if widthTemp/heightTemp != width/height:
                print('Warning, rize ratio will be changed')
            
            # save and show size change
            resizedSizeText = (
                '{}x{} --> {}x{}'
                .format(width, height, widthTemp, heightTemp)
            )
            self.vList[index]['resizedSize'] = resizedSizeText
            print(resizedSizeText)
            
            # check if resize needed
            if widthTemp == width and heightTemp == height:
                print("Skiped")
                # recored no resize needed
                self.vList[index]['resizeTime'] = '0'
                continue

            # compute resizedBitRate
            resizedBitRate = widthTemp * heightTemp * quality
            # save and show bit rate change
            resizedBitRateText = (
                '{:_.0f} --> {:_.0f} Kbits/s'
                .format(bitRate/1_000, resizedBitRate/1_000)
            )
            self.vList[index]['resizedBitRate'] = resizedBitRateText
            print(resizedBitRateText)
            bitRateParam = f'{resizedBitRate} -maxrate {resizedBitRate} -bufsize 800M '

            resizeTime = time()
            # rezize commands
            command = (
                'start /min /wait cmd /c " {}:'.format(self.path[0])
                +' & cd {}'.format(self.path)
                +' & ffmpeg -hwaccel cuda -hwaccel_output_format cuda'
                +' -i "{}"'.format(path)
                +' -map 0:a? -map 0:s? -map 0:v'
                +' -vf scale_cuda={}:{}'.format(rWidth,rHeight)
                +' -c:a copy -c:v hevc_nvenc {}'.format(self.highQualityParam)
                +' -b:v {}'.format(bitRateParam)
                +' -r {} -y'.format(frameRate)
                +' "resized\\{}" "'.format(name)
            )
            print(f'Resizing "{name}"')
            system(command)
            print("Done")
            
            resizeTime = time()-resizeTime
            resizeTime = timedelta(seconds=round(resizeTime,0))
            # recored resizing result
            self.vList[index]['resizeTime'] = str(resizeTime)
            print("Took :", str(resizeTime))
        
        # notice resize end
        self.noticeProcessEnd()
    # endregion resize
    ##################

    ###################
    # region - -upscale
    def upscale(self, upscaleFactor:int=2|3|4, quality:float=3):
        """
        Upscale video

        Parameters:
            upscaleFactor (int):
                2, 3 or 4
            
            quality (float):
                video bit rate = width x height x quality
        
        Used attributes:
            path
            vList
            highQualityParam
        
        Used functions/methodes:
            getFrames()
            frameWatch()
        
        """

        # create output folder
        if not isdir(self.path+'\\upscaled'):
            mkdir(self.path+'\\upscaled')

        for index, video in enumerate(self.vList):
                
            path = video['path']
            name = video['name']
            width = video['width']
            height = video['height']
            bitRate = video['bitRate']
            frameRate = video['r_frame_rate']

            # show current upscaling video
            print('--- {}/{} ---'.format(index+1,len(self.vList)))
            print(name)

            # save and show size change
            upscaledSizeText = (
                '{}x{} --> {}x{}'
                .format(width, height, int(width*upscaleFactor), int(height*upscaleFactor))
            )
            self.vList[index]['upscaledSize'] = upscaledSizeText
            print(upscaledSizeText)

            # compute upscale bit rate
            upscaledBitRate = width * height * quality * upscaleFactor**2
            # save and show bit rate change
            upscaledBitRateText = (
                '{:_.0f} --> {:_.0f} Kbits/s'
                .format(bitRate/1_000, upscaledBitRate/1_000)
            )
            self.vList[index]['upscaledBitRate'] = upscaledBitRateText
            print(upscaledBitRateText)
            bitRateParam = f'{upscaledBitRate} -maxrate {upscaledBitRate} -bufsize 800M '

            ######################
            # region - --get frame
            frameTime = time()

            self.getFrames(video)   # wait till end
            frameTime = time()-frameTime
            frameTime = timedelta(seconds=round(frameTime,0))
            totalFrames = len(listdir(self.path+'\\{}_tmp_frames'.format(name)))
            # recored frame time
            self.vList[index]['frameTime'] = str(frameTime)

            print("Took :", str(frameTime))
            # endregion frame
            #################

            ####################
            # region - --upscale
            upscaleTime = time()

            upscaleOutputPath = self.path+'\\{}_upscaled_frames'.format(name)
            # create upscaled frames folder if not existing
            if not isdir(upscaleOutputPath):
                mkdir(upscaleOutputPath)
                print(f'Upscaling "{name}"')

            # continue existing frames upscale
            else:
                for root, _, files in walk(upscaleOutputPath):
                    # remove upscaled frame's origin frames except last two
                    for upscaled in files[:-2]:
                        remove(root.replace('_upscaled_frames','_tmp_frames')+'\\'+upscaled)
                    # remove last two upscaled frames
                    for lastTwoUpscaled in files[-2:]:
                        remove(root+'\\'+lastTwoUpscaled)
                print(f'Continue upscaling "{name}"')
            
            command = (
                'start /min cmd /c " {}:'.format(self.path[0])
                +' & cd {}'.format(self.path)
                +' & realesrgan-ncnn-vulkan.exe'
                +' -i "{}_tmp_frames" '.format(name)
                +' -o "{}_upscaled_frames" '.format(name)
            )
            # x4 upscaleFactor
            if upscaleFactor == 4:
                command += ' -n realesrgan-x4plus-anime -f jpg -g 1"'
            # x2 and x3 upscaleFactor
            else:
                command += ' -n realesr-animevideov3 -s {} -f jpg -g 1"'.format(upscaleFactor)
            system(command)

            # frames watch
            self.frameWatch(
                outDir=(upscaleOutputPath),
                total=totalFrames
            )
            # remove frames
            rmtree(self.path+'\\{}_tmp_frames'.format(name))

            upscaleTime = time()-upscaleTime
            upscaleTime = timedelta(seconds=round(upscaleTime,0))
            # recored upscale result
            self.vList[index]['upscaleTime'] = str(upscaleTime)
            print("Took :", str(upscaleTime))
            # endregion upscale
            ###################

            ###########################
            # region - --frame to video
            frameToVideoTime = time()

            # upscaled frames to video
            command = (
                'start /min /wait cmd /c " {}:'.format(self.path[0])
                +' & cd {}'.format(self.path)
                +' & ffmpeg -hwaccel cuda -hwaccel_output_format cuda'
                +' -c:v mjpeg_cuvid -r {}'.format(frameRate)
                +' -i "{}_upscaled_frames/frame%08d.jpg" '.format(name)
                +' -hwaccel cuda'
                +' -i "{}"'.format(path)
                +' -map 0:v:0 -map 1:a? -map 1:s? -c:a copy -c:s copy -c:v hevc_nvenc'
                +' -b:v {}'.format(bitRateParam)
                +' -r {}'.format(frameRate)
                +' -y {}'.format(self.highQualityParam)
                +' "upscaled\\{}" "'.format(name)
            )
            print(f'Upscaling frame to video "{name}"')
            system(command)
            print("Done")

            # remove upscaled frames
            rmtree(upscaleOutputPath)

            frameToVideoTime = time()-frameToVideoTime
            frameToVideoTime = timedelta(seconds=round(frameToVideoTime,0))
            # recored upscale result
            self.vList[index]['frameToVideoTime'] = str(frameToVideoTime)
            print("Took :", str(frameToVideoTime))
            # endregion frame to video
            ##########################

            self.vList[index]['upscaleTotalTime'] = str(frameTime + upscaleTime + frameToVideoTime)
            print("Total time :", str(frameTime + upscaleTime + frameToVideoTime))
            
            self.vList[index]['upscaleFactor'] = upscaleFactor

        # notice upscale end
        self.noticeProcessEnd()
    # endregion upscale
    ###################

    #######################
    # region - -interpolate
    def interpolate(self, fps:float=30.0, quality:float=3):
        """
        Interpolate video to increase fps

        Parameters:
            fps (float):
                must > than original fps

            quality (float):
                video bit rate = width x height x quality
        
        Used attributes:
            path
            vList
            highQualityParam
        
        Used functions/methodes:
            getFrames()
            frameWatch()
        
        """

        # create output folder
        if not isdir(self.path+'\\interpolated'):
            mkdir(self.path+'\\interpolated')


        for index, video in enumerate(self.vList):

            path = video['path']
            name = video['name']
            width = video['width']
            height = video['height']
            bitRate = video['bitRate']
            frameRate = video['r_frame_rate']
            duration = video['duration']

            # show current resizing video
            print('--- {}/{} ---'.format(index+1,len(self.vList)))
            print(name)

            # check if interpolation needed
            if fps < frameRate:
                print("Skiped")
                print(fps, '<', frameRate)
                continue

            # save and show interpolate change
            interpolateFrame = int(duration.total_seconds() * fps)
            interpolateFrameText = (
                '{}fps --> {}fps'
                .format(frameRate, fps)
            )
            self.vList[index]['interpolateFrame'] = interpolateFrameText
            print(interpolateFrameText)

            # compute interpolate bit rate
            interpolateBitRate = width * height * quality
            # save and show bit rate change
            interpolateBitRateText = (
                '{:_.0f} --> {:_.0f} Kbits/s'
                .format(bitRate/1_000, interpolateBitRate/1_000)
            )
            self.vList[index]['interpolateBitRate'] = interpolateBitRateText
            print(interpolateBitRateText)
            bitRateParam = f'{interpolateBitRate} -maxrate {interpolateBitRate} -bufsize 800M '

            ######################
            # region - --get frame
            frameTime = time()

            self.getFrames(video)   # wait till end
            frameTime = time()-frameTime
            frameTime = timedelta(seconds=round(frameTime,0))
            totalFrames = len(listdir(self.path+'\\{}_tmp_frames'.format(name)))
            # recored frame time
            self.vList[index]['frameTime'] = str(frameTime)

            print("Took :", str(frameTime))
            # endregion frame
            #################

            ####################
            # region - --interpolate
            interpolateTime = time()

            interpolateOutputPath = self.path+'\\{}_interpolated_frames'.format(name)
            # remove empty interpolated frames folder
            if isdir(interpolateOutputPath):
                rmtree(interpolateOutputPath)

            # new frames interpolate
            mkdir(interpolateOutputPath)
            command = (
                'start /min /wait cmd /c " {}:'.format(self.path[0])
                +' & cd {}'.format(self.path)
                +' & ifrnet-ncnn-vulkan.exe'
                +' -i "{}_tmp_frames" '.format(name)
                +' -o "{}_interpolated_frames" '.format(name)
                +' -m IFRNet_GoPro -g 1 -f frame%08d.jpg'
                +' -n {}"'.format(interpolateFrame)
            )
            print(f'Interpolating "{name}"')
            system(command)

            # frames watch
            self.frameWatch(
                outDir=(interpolateOutputPath),
                total=interpolateFrame
            )
            # remove frames
            rmtree(self.path+'\\{}_tmp_frames'.format(name))

            interpolateTime = time() - interpolateTime
            interpolateTime = timedelta(seconds=round(interpolateTime,0))
            # recored interpolate result
            self.vList[index]['interpolateTime'] = str(interpolateTime)
            print("Took :", str(interpolateTime))
            # endregion interpolate
            ###################

            ###########################
            # region - --frame to video
            frameToVideoTime = time()

            # upscaled frames to video
            command = (
                'start /min /wait cmd /c " {}:'.format(self.path[0])
                +' & cd {}'.format(self.path)
                +' & ffmpeg -threads 16 -hwaccel cuda -hwaccel_output_format cuda'
                +' -c:v mjpeg_cuvid -r {}'.format(fps)
                +' -i "{}_interpolated_frames/frame%08d.jpg" '.format(name)
                +' -hwaccel cuda'
                +' -i "{}"'.format(path)
                +' -map 0:v:0 -map 1:a? -map 1:s? -c:a copy -c:s copy -c:v hevc_nvenc'
                +' -b:v {}'.format(bitRateParam)
                +' -r {}'.format(fps)
                +' -y {}'.format(self.highQualityParam)
                +' "interpolated\\{}" "'.format(name)
            )
            print(f'Interpolating frame to video "{name}"')
            system(command)
            print("Done")

            # remove upscaled frames
            rmtree(interpolateOutputPath)

            frameToVideoTime = time()-frameToVideoTime
            frameToVideoTime = timedelta(seconds=round(frameToVideoTime,0))
            # recored upscale result
            self.vList[index]['frameToVideoTime'] = str(frameToVideoTime)
            print("Took :", str(frameToVideoTime))
            # endregion frame to video
            ##########################

            self.vList[index]['interpolateTotalTime'] = str(frameTime + interpolateTime + frameToVideoTime)
            print("Total time :", self.vList[index]['interpolateTotalTime'])
            
            self.vList[index]['interpolateFrame'] = fps

        # notice interpolate end
        self.noticeProcessEnd()
    # endregion interpolate
    #######################


    ####################
    # region - -merge
    def merge(self, allVideo:bool=True, allAudio:bool=False, allSubtitle:bool=False):
        """
        Merge video0.mp4 video1.mp4 ... to video.mkv

        Parameters:
            allVideo (bool):
                set to False to keep only the first video, default=True
            
            allAudio (bool):
                set to True to keep all audio, default=False
                
            allSubtitle (bool):
                set to True to keep all subtitle, default=False
        
        Used attributes:
            path
            vList
        """
        # create output folder
        if not isdir(self.path+'\\merged'):
            mkdir(self.path+'\\merged')

        # check number of video
        if len(self.vList) <= 1:
            print("0 or 1 video is not enought to merge")
            return

        # check video length
        duration = self.vList[0]['duration']
        for video in self.vList:
            if duration != video['duration']:
                print(f'Warning, "{video["name"]}" has different duration')
        
        commandInputs = ""
        commandMap = ""
        commandMetadata = ""
        for index, video in enumerate(self.vList):

            path = video['path']
            name = video['name']

            if index == 0:
                commandInputs += f'-i "{path}" '
                commandMap += f'-map {index} '
                commandMetadata += f'-metadata:s:v:{index} title="{name}" '
                commandMetadata += f'-metadata:s:a:{index} title="{name}" '
                commandMetadata += f'-metadata:s:s:{index} title="{name}" '
            else:
                commandInputs += f'-i "{path}" '
                if allVideo:
                    commandMap += f'-map {index}:v? '
                    commandMetadata += f'-metadata:s:v:{index} title="{name}" '
                if allAudio:
                    commandMap += f'-map {index}:a? '
                    commandMetadata += f'-metadata:s:a:{index} title="{name}" '
                if allSubtitle:
                    commandMap += f'-map {index}:s? '
                    commandMetadata += f'-metadata:s:s:{index} title="{name}" '

        spendTime = time()
        command = (
            'start /min /wait cmd /c " {}:'.format(self.path[0])
            +' & cd {}'.format(self.path)
            +' & ffmpeg -hwaccel cuda'
            +' {}'.format(commandInputs)
            +' {}'.format(commandMap)
            +' -c copy'
            +' {}'.format(commandMetadata)
            +' -y "merged\\{}" "'.format(name)
        )
        print(f'Merging {len(self.vList)} videos')
        system(command)
        print("Done")
                
        spendTime = time()-spendTime
        spendTime = timedelta(seconds=round(spendTime,0))
        print("Took :", str(spendTime))
        
        # notice merging end
        self.noticeProcessEnd()
    # endregion merge
    ####################


    # endregion processes
    #####################




def inputInt(selections:list=[]) -> int:
    while True:
        # get int
        entered = input()
        try:
            entered = int(entered)
        except:
            print(f'{entered} is not an integer')
        # no selection constrain
        if selections == []:
            return entered
        # check if in selections
        elif entered in selections:
            return entered
        else:
            print(f'{entered} is not in {selections}')



if __name__ == '__main__':

    vs = VideoScript()

    vs.getVideo(folderDepthLimit=0)
    vs.getVideoInfo()

    # # get frame test
    # for video in vs.vList:
    #     vs.getFrames(video)

    print('Select a process :')
    print('1 - optimize')
    print('2 - resize')
    print('3 - upscale')
    print('4 - interpolate')
    print('5 - merge')

    process = inputInt(selections=[1,2,3,4,5])

    if process == 1:
        vs.optimize(3)
        print(vs.vList)

    elif process == 2:
        vs.resize(1920, -1, 3)
        print(vs.vList)

    elif process == 3:
        vs.upscale(2, 3)
        print(vs.vList)

    elif process == 4:
        vs.interpolate(60.0, 3)
        print(vs.vList)

    elif process == 5:
        vs.merge(True, False, False)
        print(vs.vList)

    input("Press enter to exit")

        